"""Rule-definition registry loader.

Keeps rule semantics in a maintainable JSON config (rules/registry.json)
instead of hard-coding them into the LLM prompt. The template fallback path
and the get_rule_definition tool both read from here.
"""
from __future__ import annotations

import json
from pathlib import Path

from agent.core.models import RuleDefinition

_REGISTRY_PATH = Path(__file__).resolve().parent / "registry.json"

_registry: dict[str, RuleDefinition] | None = None


def load_registry() -> dict[str, RuleDefinition]:
    global _registry
    if _registry is None:
        raw = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
        _registry = {rid: RuleDefinition(**data) for rid, data in raw.items()}
    return _registry


def get_rule(rule_id: str) -> RuleDefinition | None:
    return load_registry().get(rule_id)


def all_rules() -> list[RuleDefinition]:
    return sorted(load_registry().values(), key=lambda r: r.rule_id)


def heuristic_rule_ids() -> set[str]:
    """Rules whose results are candidates requiring human review."""
    return {rid for rid, r in load_registry().items() if r.type == "heuristic"}
