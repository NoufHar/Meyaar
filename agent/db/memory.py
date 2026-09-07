"""In-memory repository for tests and offline demos.

Mimics PostgresRepository behaviour without a server. Seed with validation
results + a fake feature store; analyses are kept in a list.
"""
from __future__ import annotations

import json
import threading
from typing import Optional

from agent.core.models import ErrorAnalysis, ValidationResult
from agent.db.base import Repository


class InMemoryRepository(Repository):
    def __init__(self, results: Optional[list[ValidationResult]] = None,
                 features: Optional[dict[str, dict[str, dict]]] = None,
                 analyses: Optional[list[ErrorAnalysis]] = None):
        self._results: list[ValidationResult] = list(results or [])
        # features: {layer_name: {feature_id: context_dict}}
        self._features: dict[str, dict[str, dict]] = features or {}
        self._analyses: list[ErrorAnalysis] = list(analyses or [])
        self._remediation: list[dict] = []
        self._repaired: set[tuple[str, str]] = set()
        self._run_summaries: dict[str, dict] = {}
        self._lock = threading.Lock()

    def seed_feature(self, layer_name: str, feature_id: str, context: dict) -> None:
        self._features.setdefault(layer_name, {})[feature_id] = context

    # ── reads ────────────────────────────────────────────────────────────
    def fetch_results(self, run_id: str, rule_id: Optional[str] = None,
                      layer_name: Optional[str] = None,
                      feature_id: Optional[str] = None,
                      severity: Optional[str] = None) -> list[ValidationResult]:
        out = [r for r in self._results if r.run_id == run_id]
        if rule_id:
            out = [r for r in out if r.rule_id == rule_id]
        if layer_name:
            out = [r for r in out if r.layer_name == layer_name]
        if feature_id:
            out = [r for r in out if r.feature_id == feature_id]
        if severity:
            out = [r for r in out if r.severity == severity]
        out.sort(key=lambda r: (r.layer_name, r.rule_id, r.result_id))
        return out

    def fetch_feature_context(self, layer_name: str, feature_id: str) -> Optional[dict]:
        return self._features.get(layer_name, {}).get(feature_id)

    def fetch_related_features(self, layer_name: str,
                               feature_ids: list[str]) -> dict[str, dict]:
        layer = self._features.get(layer_name, {})
        return {fid: layer[fid] for fid in feature_ids if fid in layer}

    def query_readonly(self, sql: str, params: Optional[dict] = None) -> list[dict]:
        from agent.tools.sql_guard import assert_readonly_sql
        assert_readonly_sql(sql)
        if not sql.strip().lower().startswith("select"):
            raise ValueError("InMemoryRepository only supports SELECT")
        return []  # no real tables; guard behaviour is what matters in tests

    # ── reads: spatial measurements ───────────────────────────────────────
    def fetch_spatial_measurements(self, layer_name: str,
                                   feature_ids: list[str],
                                   other_feature_id: Optional[str] = None
                                   ) -> dict[str, dict]:
        layer = self._features.get(layer_name, {})
        out: dict[str, dict] = {}
        for fid in feature_ids:
            ctx = layer.get(fid)
            if ctx is None:
                continue                     # never fabricate a missing feature
            geom_type = ctx.get("geometry_type")
            out[fid] = {
                "feature_id": fid,
                "geometry_type": geom_type,
                "srid": ctx.get("srid"),
                "is_valid": ctx.get("is_valid"),
                "is_empty": ctx.get("is_empty"),
                # Seed explicit measurement values in tests; None = N/A.
                "length_m": ctx.get("length_m"),
                "area_m2": ctx.get("area_m2"),
                "vertex_count": ctx.get("vertex_count"),
                "centroid": ctx.get("centroid"),
                "bbox": ([ctx["x_min"], ctx["y_min"], ctx["x_max"], ctx["y_max"]]
                         if all(k in ctx for k in ("x_min", "y_min", "x_max", "y_max"))
                         else None),
            }
            if other_feature_id:
                out[fid].update({
                    "other_feature_id": other_feature_id,
                    "distance_m": ctx.get("distance_m"),
                    "intersects": ctx.get("intersects"),
                    "overlap_area_m2": ctx.get("overlap_area_m2"),
                })
        return out

    # ── writes: remediation ───────────────────────────────────────────────
    def apply_geometry_repair(self, layer_name: str, feature_id: str) -> dict:
        from agent.db.base import RemediationError
        ctx = self._features.get(layer_name, {}).get(feature_id)
        if ctx is None:
            raise RemediationError(
                f"geometry repair: feature {feature_id!r} not found in layer "
                f"{layer_name!r} — nothing safe to mutate")
        if ctx.get("repair_fails"):
            raise RemediationError(
                f"geometry repair: simulated ST_MakeValid failure for "
                f"{feature_id!r} — rolled back")
        with self._lock:
            self._repaired.add((layer_name, feature_id))
        geom_type = ctx.get("geometry_type")
        wkt = ctx.get("geometry_wkt", "<geometry>")
        return {
            "feature_id": feature_id, "layer_name": layer_name,
            "before": {"geometry_type": geom_type, "srid": ctx.get("srid"),
                       "geojson": wkt, "is_valid": False},
            "after": {"geometry_type": geom_type, "srid": ctx.get("srid"),
                      "geojson": wkt, "is_valid": True},
            "changed": True,
        }

    def save_remediation_records(self, records: list[dict]) -> int:
        with self._lock:
            for rec in records:
                self._remediation = [
                    r for r in self._remediation
                    if not (r["run_id"] == rec["run_id"]
                            and r["result_id"] == rec["result_id"])]
                self._remediation.append(dict(rec))
        return len(records)

    def fetch_remediation_records(self, run_id: str) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._remediation if r["run_id"] == run_id]

    def save_run_summary(self, run_id: str, narrative: str,
                         agent_model: str = "",
                         counts: Optional[dict] = None) -> bool:
        with self._lock:
            self._run_summaries[run_id] = {
                "run_id": run_id, "narrative": narrative,
                "agent_model": agent_model or "",
                "counts": dict(counts or {}),
            }
        return True

    def fetch_run_summary(self, run_id: str) -> Optional[dict]:
        with self._lock:
            row = self._run_summaries.get(run_id)
            return dict(row) if row else None

    @property
    def repaired_features(self) -> set[tuple[str, str]]:
        """(layer_name, feature_id) pairs repaired in this instance (tests)."""
        return set(self._repaired)

    # ── writes ───────────────────────────────────────────────────────────
    def save_analyses(self, analyses: list[ErrorAnalysis]) -> int:
        with self._lock:
            for a in analyses:
                self._analyses = [x for x in self._analyses
                                  if not (x.run_id == a.run_id and x.result_id == a.result_id)]
                self._analyses.append(a)
        return len(analyses)

    def fetch_analyses(self, run_id: str) -> list[ErrorAnalysis]:
        with self._lock:
            return [a for a in self._analyses if a.run_id == run_id]


def load_fixture_results(path: str) -> list[ValidationResult]:
    """Load a JSON array of validation_results rows from a fixture file."""
    data = json.loads(open(path, encoding="utf-8").read())
    return [ValidationResult(**row) for row in data]
