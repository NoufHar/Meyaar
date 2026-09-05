"""Database repository interface for the Error Analysis Agent.

The graph and tools depend on this interface, never on a concrete driver —
tests inject the InMemoryRepository, production uses PostgresRepository.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from agent.core.models import ErrorAnalysis, ValidationResult


class Repository(ABC):
    """Read-only access to validation results + feature context, and write
    access to the agent's OWN analysis table (never to source tables)."""

    # ── reads (validation_results + PostGIS context) ─────────────────────
    @abstractmethod
    def fetch_results(self, run_id: str, rule_id: Optional[str] = None,
                      layer_name: Optional[str] = None,
                      feature_id: Optional[str] = None,
                      severity: Optional[str] = None) -> list[ValidationResult]:
        """Get validation results for a run, optionally filtered."""

    @abstractmethod
    def fetch_feature_context(self, layer_name: str,
                              feature_id: str) -> Optional[dict]:
        """Lightweight context for one feature: id, geometry type, SRID,
        centroid, bbox, and a few attributes. NEVER returns full geometries
        to the LLM."""

    @abstractmethod
    def fetch_related_features(self, layer_name: str,
                               feature_ids: list[str]) -> dict[str, dict]:
        """Bulk context for several features; missing ids are absent from
        the returned dict (never fabricated)."""

    @abstractmethod
    def query_readonly(self, sql: str, params: Optional[dict] = None) -> list[dict]:
        """Execute a read-only SQL statement and return rows as dicts.
        Raises ValueError on anything that is not a read-only query."""

    # ── writes (agent_error_analysis only) ───────────────────────────────
    @abstractmethod
    def save_analyses(self, analyses: list[ErrorAnalysis]) -> int:
        """Insert/upsert agent analyses. Returns number saved."""

    @abstractmethod
    def fetch_analyses(self, run_id: str) -> list[ErrorAnalysis]:
        """Return previously saved analyses for a run."""

    # ── summary helpers ──────────────────────────────────────────────────
    def build_summary(self, results: list[ValidationResult],
                      analyses: list[ErrorAnalysis]) -> dict:
        """Deterministic run-level rollup shared by graph + API."""
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        by_rule: dict[str, int] = {}
        by_layer: dict[str, int] = {}
        for r in results:
            sev = r.severity if r.severity in counts else "low"
            counts[sev] += 1
            by_rule[r.rule_id] = by_rule.get(r.rule_id, 0) + 1
            by_layer[r.layer_name] = by_layer.get(r.layer_name, 0) + 1
        most_common = max(by_rule.items(), key=lambda kv: kv[1])[0] if by_rule else None
        most_common_error = None
        if most_common:
            from agent.rules.registry import get_rule
            rd = get_rule(most_common)
            most_common_error = rd.error_type if rd else most_common
        return {
            "total_errors": len(results),
            "critical_errors": counts["critical"],
            "high_errors": counts["high"],
            "medium_errors": counts["medium"],
            "low_errors": counts["low"],
            "most_common_error": most_common_error,
            "counts_by_rule": dict(sorted(by_rule.items())),
            "counts_by_layer": dict(sorted(by_layer.items())),
            "human_review_pending": sum(1 for a in analyses if a.human_review_required),
            "analyzed": len(analyses),
        }

    def priority_actions(self, summary: dict) -> list[str]:
        """Deterministic priority ordering: critical geometry first, then
        critical general, heuristics last (they need review anyway)."""
        actions: list[str] = []
        if summary.get("critical_errors"):
            actions.append("Resolve critical errors first (missing geometry / CRS / coordinates)")
        if summary.get("high_errors"):
            actions.append("Fix high-severity errors before re-running validation")
        if summary.get("human_review_pending"):
            actions.append("Review heuristic topology candidates flagged for human review")
        if summary.get("analyzed", 0) and not actions:
            actions.append("No blocking errors; verify medium/low items during cleanup")
        return actions
