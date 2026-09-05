"""Agent tools — context retrieval for the Error Analysis Agent.

Each tool is a plain, typed, documented callable that talks to the injected
Repository. Tools never fabricate: a missing feature returns None/{} and the
caller decides (-> insufficient_context), never an invented row.

A REGISTRY maps names -> callables so the LLM node can bind them later and so
tests can exercise them directly.
"""
from __future__ import annotations

from typing import Optional

from agent.core.models import RuleDefinition, ValidationResult
from agent.db.base import Repository
from agent.rules.registry import get_rule

# ── 1. get_validation_results ───────────────────────────────────────────────
def get_validation_results(repo: Repository, run_id: str,
                           rule_id: Optional[str] = None,
                           layer_name: Optional[str] = None,
                           feature_id: Optional[str] = None,
                           severity: Optional[str] = None) -> list[dict]:
    """Return validation_results rows for a run, optionally filtered by
    rule_id / layer_name / feature_id / severity. The rule engine is the
    source of truth for detection; this tool only reads its output."""
    rows = repo.fetch_results(run_id, rule_id=rule_id, layer_name=layer_name,
                              feature_id=feature_id, severity=severity)
    return [r.model_dump() for r in rows]


# ── 2. get_feature_context ──────────────────────────────────────────────────
def get_feature_context(repo: Repository, layer_name: str,
                        feature_id: str) -> Optional[dict]:
    """Return lightweight context for ONE feature (geometry type, SRID,
    centroid, bbox). Returns None when the feature does not exist — never
    invents a location. Full geometries are intentionally not returned."""
    return repo.fetch_feature_context(layer_name, feature_id)


# ── 3. get_related_features ─────────────────────────────────────────────────
def get_related_features(repo: Repository, layer_name: str,
                         feature_ids: list[str]) -> dict[str, dict]:
    """Return contexts for several features of the same layer (used when a
    result references another feature, e.g. 'BLD_102 overlaps BLD_157').
    Missing ids are simply absent from the result."""
    return repo.fetch_related_features(layer_name, feature_ids)


# ── 4. query_postgis (read-only) ────────────────────────────────────────────
def query_postgis(repo: Repository, sql: str,
                  params: Optional[dict] = None) -> list[dict]:
    """Run a controlled READ-ONLY spatial/SQL query and return rows as dicts.
    Rejects anything that is not a single SELECT/WITH statement; the DB
    connection is additionally opened in read-only mode."""
    return repo.query_readonly(sql, params)


# Alias matching the role's canonical tool name.
query_postgis_readonly = query_postgis


# ── 5. get_rule_definition ──────────────────────────────────────────────────
def get_rule_definition(rule_id: str) -> Optional[dict]:
    """Return the maintainable definition for a rule (description, baseline
    severity, deterministic vs heuristic, human-review flag)."""
    rd: Optional[RuleDefinition] = get_rule(rule_id)
    return rd.model_dump() if rd else None


def _first_line(doc: Optional[str]) -> str:
    return (doc or "").strip().splitlines()[0] if (doc or "").strip() else ""


# One inspectable registry of the agent tools (name -> callable taking repo).
TOOL_REGISTRY: dict[str, object] = {
    "get_validation_results": get_validation_results,
    "get_feature_context": get_feature_context,
    "get_related_features": get_related_features,
    "query_postgis_readonly": query_postgis_readonly,
    "get_rule_definition": get_rule_definition,
}


def tool_descriptions() -> list[dict]:
    """Schemas shown to the LLM when the analysis node binds tools."""
    return [
        {"name": "get_validation_results",
         "description": _first_line(get_validation_results.__doc__),
         "args": ["run_id", "rule_id?", "layer_name?", "feature_id?", "severity?"]},
        {"name": "get_feature_context",
         "description": _first_line(get_feature_context.__doc__),
         "args": ["layer_name", "feature_id"]},
        {"name": "get_related_features",
         "description": _first_line(get_related_features.__doc__),
         "args": ["layer_name", "feature_ids"]},
        {"name": "query_postgis_readonly",
         "description": _first_line(query_postgis.__doc__),
         "args": ["sql", "params?"]},
        {"name": "get_rule_definition",
         "description": _first_line(get_rule_definition.__doc__),
         "args": ["rule_id"]},
    ]
