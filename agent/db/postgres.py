"""PostgreSQL/PostGIS repository implementation (SQLAlchemy).

Connection settings come from agent.core.config; every connection is opened
with default_transaction_read_only=on as a second line of defense — even a
buggy query cannot write through this engine.
"""
from __future__ import annotations

import json
import re
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

    # ── reads: spatial measurements (Part 1) ──────────────────────────────
    _LAYER_RE = re.compile(r"^[a-z_][a-z0-9_]*$")

    def _assert_layer_name(self, layer_name: str) -> str:
        if not isinstance(layer_name, str) or not self._LAYER_RE.match(layer_name):
            raise ValueError(f"invalid layer name: {layer_name!r}")
        return layer_name

    def fetch_spatial_measurements(self, layer_name: str,
                                   feature_ids: list[str],
                                   other_feature_id: Optional[str] = None
                                   ) -> dict[str, dict]:
        """Real PostGIS measurements over the read-only engine. NULL/absent
        geometry yields None fields (never invented numbers)."""
        self._assert_layer_name(layer_name)
        ids = [fid for fid in (feature_ids or []) if fid is not None]
        if not ids:
            return {}
        id_col = self._id_column(layer_name)
        out: dict[str, dict] = {}
        sql = f"""
            SELECT {id_col} AS feature_id,
                   GeometryType(geometry)                     AS geometry_type,
                   ST_SRID(geometry)                          AS srid,
                   ST_IsValid(geometry)                       AS is_valid,
                   ST_IsEmpty(geometry)                       AS is_empty,
                   CASE WHEN ST_SRID(geometry) = 4326
                        THEN ST_Length(geometry::geography) END AS length_m,
                   CASE WHEN ST_SRID(geometry) = 4326
                        THEN ST_Area(geometry::geography) END   AS area_m2,
                   ST_NPoints(geometry)                       AS vertex_count,
                   ST_AsText(ST_Centroid(geometry))           AS centroid,
                   ST_XMin(geometry) AS x_min, ST_YMin(geometry) AS y_min,
                   ST_XMax(geometry) AS x_max, ST_YMax(geometry) AS y_max
            FROM {layer_name}
            WHERE {id_col} IN ({", ".join(f":id_{i}" for i in range(len(ids)))})
        """
        params = {f"id_{i}": fid for i, fid in enumerate(ids)}
        try:
            with self.readonly_engine.connect() as conn:
                rows = conn.execute(text(sql), params).mappings().all()
        except Exception:
            return {}   # tool failure must not kill the run
        for r in rows:
            d = dict(r)
            fid = str(d["feature_id"])
            bbox = None
            if d.get("x_min") is not None:
                bbox = [d["x_min"], d["y_min"], d["x_max"], d["y_max"]]
            for k in ("x_min", "y_min", "x_max", "y_max"):
                d.pop(k, None)
            d["bbox"] = bbox
            out[fid] = d

        # Relationship block (distance / intersection / overlap area).
        if other_feature_id:
            rel = self._measure_relationship(layer_name, id_col,
                                             list(ids), other_feature_id)
            for fid, rel_row in rel.items():
                out.setdefault(fid, {"feature_id": fid}).update(rel_row)
        return out

    def _measure_relationship(self, layer_name: str, id_col: str,
                              feature_ids: list[str],
                              other_feature_id: str) -> dict[str, dict]:
        """One query computing distance/intersection/overlap between each
        requested feature and `other_feature_id`."""
        out: dict[str, dict] = {}
        sql = f"""
            SELECT a.{id_col} AS feature_id,
                   ST_Distance(a.geometry::geography, b.geometry::geography)
                       AS distance_m,
                   ST_Intersects(a.geometry, b.geometry) AS intersects,
                   CASE WHEN ST_Intersects(a.geometry, b.geometry)
                             AND ST_SRID(a.geometry) = 4326
                        THEN ST_Area(ST_Intersection(a.geometry, b.geometry)
                                     ::geography)
                   END AS overlap_area_m2
            FROM {layer_name} a, {layer_name} b
            WHERE a.{id_col} IN ({", ".join(f":id_{i}" for i in range(len(feature_ids)))})
              AND b.{id_col} = :other_id
        """
        params = {f"id_{i}": fid for i, fid in enumerate(feature_ids)}
        params["other_id"] = other_feature_id
        try:
            with self.readonly_engine.connect() as conn:
                rows = conn.execute(text(sql), params).mappings().all()
        except Exception:
            return {}
        for r in rows:
            d = dict(r)
            d["other_feature_id"] = other_feature_id
            out[str(d.pop("feature_id"))] = d
        return out

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

    # ── writes: whitelisted remediation + audit (Part 8 / 9) ─────────────
    def apply_geometry_repair(self, layer_name: str, feature_id: str) -> dict:
        """The ONLY automatic source-table mutation in the agent.

        Transactional ST_MakeValid repair of one feature, guarded: the
        feature must exist, its geometry must currently be invalid, and the
        repaired geometry must be valid and non-empty. Any failure raises
        (engine.begin() rolls back) and the caller records it.
        """
        from agent.db.base import RemediationError

        self._assert_layer_name(layer_name)
        id_col = self._id_column(layer_name)
        with self.engine.begin() as conn:
            before = conn.execute(
                text(f"""SELECT ST_AsGeoJSON(geometry) AS geojson,
                                ST_IsValid(geometry)   AS is_valid,
                                GeometryType(geometry) AS geometry_type,
                                ST_SRID(geometry)      AS srid
                         FROM {layer_name}
                         WHERE {id_col} = :fid"""),
                {"fid": feature_id}).mappings().first()
            if before is None:
                raise RemediationError(
                    f"geometry repair: feature {feature_id!r} not found in layer "
                    f"{layer_name!r} — nothing safe to mutate")
            if before["geojson"] is None:
                raise RemediationError(
                    f"geometry repair: feature {feature_id!r} has NULL geometry — "
                    "repair cannot invent one")
            if before["is_valid"]:
                return {
                    "feature_id": feature_id, "layer_name": layer_name,
                    "before": {"note": "already valid", "geojson": before["geojson"]},
                    "after": {"note": "no change needed", "geojson": before["geojson"]},
                    "changed": False,
                }
            # ST_MakeValid may split a self-intersecting ring into a Multi
            # geometry. When exactly ONE part results, collapse it back to the
            # single geometry so it stays storable in a Polygon/LineString
            # typed column; multi-part results on a single-typed column are
            # refused below (transaction rolls back, failure is recorded).
            try:
                after = conn.execute(
                    text(f"""UPDATE {layer_name}
                             SET geometry = CASE
                                 WHEN ST_GeometryType(ST_MakeValid(geometry))
                                          LIKE 'Multi%'
                                  AND ST_NumGeometries(ST_MakeValid(geometry)) = 1
                                 THEN ST_GeometryN(ST_MakeValid(geometry), 1)
                                 ELSE ST_MakeValid(geometry)
                             END
                             WHERE {id_col} = :fid
                             RETURNING ST_AsGeoJSON(geometry) AS geojson,
                                       ST_IsValid(geometry)   AS is_valid,
                                       ST_IsEmpty(geometry)   AS is_empty,
                                       GeometryType(geometry) AS geometry_type"""),
                    {"fid": feature_id}).mappings().first()
            except Exception as exc:
                raise RemediationError(
                    f"geometry repair: ST_MakeValid output could not be stored "
                    f"for {feature_id!r} (the repair changes the geometry type "
                    f"incompatibly with the layer column, e.g. MultiPolygon vs "
                    f"Polygon) — rolled back; human re-digitization required. "
                    f"Details: {exc}") from exc
            if after is None or not after["is_valid"] or after["is_empty"]:
                raise RemediationError(
                    f"geometry repair: ST_MakeValid did not yield a valid, "
                    f"non-empty geometry for {feature_id!r} — rolled back")
        return {
            "feature_id": feature_id, "layer_name": layer_name,
            "before": {"geometry_type": before["geometry_type"],
                       "srid": before["srid"],
                       "geojson": before["geojson"]},
            "after": {"geometry_type": after["geometry_type"],
                      "is_valid": after["is_valid"],
                      "geojson": after["geojson"]},
            "changed": True,
        }

    def save_remediation_records(self, records: list[dict]) -> int:
        if not records:
            return 0
        sql = """
        INSERT INTO public.agent_remediation_actions (
            run_id, result_id, layer_name, feature_id, rule_id,
            action, remediation_type, status, issue, reason,
            recommended_action, before_state, after_state,
            agent_model, human_review_required
        ) VALUES (
            :run_id, :result_id, :layer_name, :feature_id, :rule_id,
            :action, :remediation_type, :status, :issue, :reason,
            :recommended_action, :before_state, :after_state,
            :agent_model, :human_review_required
        )
        ON CONFLICT (run_id, result_id) DO UPDATE SET
            layer_name = EXCLUDED.layer_name,
            feature_id = EXCLUDED.feature_id,
            rule_id = EXCLUDED.rule_id,
            action = EXCLUDED.action,
            remediation_type = EXCLUDED.remediation_type,
            status = EXCLUDED.status,
            issue = EXCLUDED.issue,
            reason = EXCLUDED.reason,
            recommended_action = EXCLUDED.recommended_action,
            before_state = EXCLUDED.before_state,
            after_state = EXCLUDED.after_state,
            agent_model = EXCLUDED.agent_model,
            human_review_required = EXCLUDED.human_review_required,
            executed_at = CURRENT_TIMESTAMP
        """
        with self.engine.begin() as conn:
            for rec in records:
                conn.execute(text(sql), {
                    "run_id": rec["run_id"], "result_id": rec["result_id"],
                    "layer_name": rec["layer_name"],
                    "feature_id": rec.get("feature_id"),
                    "rule_id": rec["rule_id"],
                    "action": rec["action"],
                    "remediation_type": rec.get("remediation_type"),
                    "status": rec["status"],
                    "issue": rec.get("issue", ""),
                    "reason": rec.get("reason", ""),
                    "recommended_action": rec.get("recommended_action"),
                    "before_state": json.dumps(rec.get("before_state") or {}),
                    "after_state": json.dumps(rec.get("after_state") or {}),
                    "agent_model": rec.get("agent_model", ""),
                    "human_review_required": bool(rec.get("human_review_required")),
                })
        return len(records)

    def fetch_remediation_records(self, run_id: str) -> list[dict]:
        sql = """
        SELECT remediation_id, run_id, result_id, layer_name, feature_id,
               rule_id, action, remediation_type, status, issue, reason,
               recommended_action, before_state, after_state, agent_model,
               human_review_required, executed_at::text AS executed_at
        FROM public.agent_remediation_actions
        WHERE run_id = :run_id
        ORDER BY layer_name, rule_id, result_id
        """
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), {"run_id": run_id}).mappings().all()
        out = []
        for r in rows:
            d = dict(r)
            if d.get("run_id") is not None:
                d["run_id"] = str(d["run_id"])
            for key in ("before_state", "after_state"):
                val = d.get(key)
                d[key] = json.loads(val) if isinstance(val, str) else (val or {})
            out.append(d)
        return out

    # ── run-level executive summary ───────────────────────────────────────
    def save_run_summary(self, run_id: str, narrative: str,
                         agent_model: str = "",
                         counts: Optional[dict] = None) -> bool:
        sql = """
        INSERT INTO public.agent_run_summaries (run_id, narrative, agent_model, counts)
        VALUES (:run_id, :narrative, :agent_model, :counts)
        ON CONFLICT (run_id) DO UPDATE SET
            narrative = EXCLUDED.narrative,
            agent_model = EXCLUDED.agent_model,
            counts = EXCLUDED.counts,
            created_at = CURRENT_TIMESTAMP
        """
        with self.engine.begin() as conn:
            conn.execute(text(sql), {
                "run_id": run_id,
                "narrative": narrative,
                "agent_model": agent_model or None,
                "counts": json.dumps(counts or {}),
            })
        return True

    def fetch_run_summary(self, run_id: str) -> Optional[dict]:
        sql = """
        SELECT run_id, narrative, agent_model, counts,
               created_at::text AS created_at
        FROM public.agent_run_summaries
        WHERE run_id = :run_id
        """
        with self.engine.connect() as conn:
            row = conn.execute(text(sql), {"run_id": run_id}).mappings().first()
        if row is None:
            return None
        d = dict(row)
        if d.get("run_id") is not None:
            d["run_id"] = str(d["run_id"])
        counts = d.get("counts")
        d["counts"] = json.loads(counts) if isinstance(counts, str) else (counts or {})
        return d
