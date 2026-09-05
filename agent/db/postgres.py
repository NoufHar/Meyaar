"""PostgreSQL/PostGIS repository implementation (SQLAlchemy).

Connection settings come from agent.core.config; every connection is opened
with default_transaction_read_only=on as a second line of defense — even a
buggy query cannot write through this engine.
"""
from __future__ import annotations

import json
from typing import Optional

from sqlalchemy import create_engine, text

from agent.core.config import settings
from agent.core.models import ErrorAnalysis, ValidationResult
from agent.db.base import Repository


class PostgresRepository(Repository):
    def __init__(self, database_url: Optional[str] = None):
        url = database_url or settings.database_url
        self._url = url
        # Normal engine: used ONLY for the agent's own table
        # (save_analyses / fetch_analyses).
        self.engine = create_engine(url, pool_pre_ping=True)
        # Read-only engine: every query/context/tool connection opens with
        # default_transaction_read_only=on so even a buggy query cannot write
        # to production GIS tables (defense in depth with the SQL guard).
        self.readonly_engine = create_engine(
            url,
            connect_args={"options": settings.db_read_only_options},
            pool_pre_ping=True,
        )
        self._id_col_cache: dict[str, str] = {}

    def _id_column(self, layer_name: str) -> str:
        """The partner insertion always adds a standard 'feature_id' column
        (roads + buildings); fall back to 'id' only if it is absent."""
        if layer_name in self._id_col_cache:
            return self._id_col_cache[layer_name]
        col = "id"
        try:
            with self.readonly_engine.connect() as conn:
                exists = conn.execute(
                    text("""SELECT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema='public' AND table_name=:t AND column_name='feature_id')"""),
                    {"t": layer_name}).scalar()
            if exists:
                col = "feature_id"
        except Exception:
            col = "feature_id" if "building" in layer_name else "id"
        self._id_col_cache[layer_name] = col
        return col

    # ── reads ────────────────────────────────────────────────────────────
    def fetch_results(self, run_id: str, rule_id: Optional[str] = None,
                      layer_name: Optional[str] = None,
                      feature_id: Optional[str] = None,
                      severity: Optional[str] = None) -> list[ValidationResult]:
        sql = ("SELECT result_id, run_id, layer_name, feature_id, rule_id, "
               "error_type, severity, details, detected_at::text AS detected_at "
               "FROM public.validation_results WHERE run_id = :run_id")
        params: dict = {"run_id": run_id}
        if rule_id:
            sql += " AND rule_id = :rule_id"
            params["rule_id"] = rule_id
        if layer_name:
            sql += " AND layer_name = :layer_name"
            params["layer_name"] = layer_name
        if feature_id:
            sql += " AND feature_id = :feature_id"
            params["feature_id"] = feature_id
        if severity:
            sql += " AND severity = :severity"
            params["severity"] = severity
        sql += " ORDER BY layer_name, rule_id, result_id"
        with self.readonly_engine.connect() as conn:
            rows = conn.execute(text(sql), params).mappings().all()
        out = []
        for r in rows:
            d = dict(r)
            if d.get("run_id") is not None:
                d["run_id"] = str(d["run_id"])   # psycopg2 returns UUID objects
            out.append(ValidationResult(**d))
        return out

    def _context_rows(self, layer_name: str, feature_ids: list[str]) -> dict[str, dict]:
        """One batched query for many feature contexts (IN clause)."""
        ids = [fid for fid in feature_ids if fid is not None]
        if not ids:
            return {}
        id_col = self._id_column(layer_name)
        binds = ", ".join(f":id_{i}" for i in range(len(ids)))
        params = {f"id_{i}": fid for i, fid in enumerate(ids)}
        sql = f"""
            SELECT {id_col} AS feature_id,
                   '{layer_name}' AS layer_name,
                   GeometryType(geometry)      AS geometry_type,
                   ST_SRID(geometry)           AS srid,
                   ST_AsText(ST_Centroid(geometry)) AS centroid,
                   ST_XMin(geometry) AS x_min, ST_YMin(geometry) AS y_min,
                   ST_XMax(geometry) AS x_max, ST_YMax(geometry) AS y_max
            FROM {layer_name}
            WHERE {id_col} IN ({binds})
        """
        try:
            with self.readonly_engine.connect() as conn:
                rows = conn.execute(text(sql), params).mappings().all()
            return {str(r["feature_id"]): dict(r) for r in rows}
        except Exception:
            return {}

    def fetch_feature_context(self, layer_name: str, feature_id: str) -> Optional[dict]:
        return self._context_rows(layer_name, [feature_id]).get(feature_id)

    def fetch_related_features(self, layer_name: str,
                               feature_ids: list[str]) -> dict[str, dict]:
        return self._context_rows(layer_name, feature_ids)

    def query_readonly(self, sql: str, params: Optional[dict] = None) -> list[dict]:
        from agent.tools.sql_guard import assert_readonly_sql
        assert_readonly_sql(sql)          # static guard (defense in depth)
        with self.readonly_engine.connect() as conn:
            rows = conn.execute(text(sql), params or {}).mappings().all()
        return [dict(r) for r in rows]

    # ── writes: agent_error_analysis only ────────────────────────────────
    def save_analyses(self, analyses: list[ErrorAnalysis]) -> int:
        if not analyses:
            return 0
        sql = """
        INSERT INTO public.agent_error_analysis (
            run_id, result_id, layer_name, feature_id, rule_id, error_type,
            severity, status, explanation, cause, recommendation,
            human_review_required, related_features, insufficient_context, agent_model
        ) VALUES (
            :run_id, :result_id, :layer_name, :feature_id, :rule_id, :error_type,
            :severity, :status, :explanation, :cause, :recommendation,
            :human_review_required, :related_features, :insufficient_context, :agent_model
        )
        ON CONFLICT (run_id, result_id) DO UPDATE SET
            status = EXCLUDED.status,
            explanation = EXCLUDED.explanation,
            cause = EXCLUDED.cause,
            recommendation = EXCLUDED.recommendation,
            human_review_required = EXCLUDED.human_review_required,
            related_features = EXCLUDED.related_features,
            insufficient_context = EXCLUDED.insufficient_context,
            agent_model = EXCLUDED.agent_model,
            analyzed_at = CURRENT_TIMESTAMP
        """
        with self.engine.begin() as conn:
            for a in analyses:
                conn.execute(text(sql), {
                    "run_id": a.run_id, "result_id": a.result_id,
                    "layer_name": a.layer_name, "feature_id": a.feature_id,
                    "rule_id": a.rule_id, "error_type": a.error_type,
                    "severity": a.severity, "status": a.status,
                    "explanation": a.explanation, "cause": a.cause,
                    "recommendation": a.recommendation,
                    "human_review_required": a.human_review_required,
                    "related_features": json.dumps(a.related_features),
                    "insufficient_context": a.insufficient_context,
                    "agent_model": a.agent_model,
                })
        return len(analyses)

    def fetch_analyses(self, run_id: str) -> list[ErrorAnalysis]:
        sql = """
        SELECT result_id, run_id, layer_name, feature_id, rule_id, error_type,
               severity, status, explanation, cause, recommendation,
               human_review_required, related_features, insufficient_context, agent_model
        FROM public.agent_error_analysis
        WHERE run_id = :run_id
        ORDER BY layer_name, rule_id, result_id
        """
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), {"run_id": run_id}).mappings().all()
        out = []
        for r in rows:
            d = dict(r)
            if d.get("run_id") is not None:
                d["run_id"] = str(d["run_id"])   # psycopg2 returns UUID objects
            rf = d.get("related_features")
            d["related_features"] = json.loads(rf) if isinstance(rf, str) else (rf or [])
            out.append(ErrorAnalysis(**d))
        return out
