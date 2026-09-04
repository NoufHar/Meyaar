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
