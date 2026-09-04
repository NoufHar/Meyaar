"""Rule registry + rule-definition tests for all 13 engine rules."""
from __future__ import annotations

import pytest

from agent.rules.registry import all_rules, get_rule, heuristic_rule_ids
from agent.tools import get_rule_definition

EXPECTED = {
    # rule: (baseline_severity, type, requires_human_review)
    "BLD001": ("high", "deterministic", False),
    "BLD002": ("medium", "deterministic", False),
    "BLD003": ("high", "deterministic", False),
    "BLD004": ("critical", "deterministic", False),
    "RD001": ("high", "heuristic", True),
    "RD002": ("high", "heuristic", True),
    "RD003": ("medium", "deterministic", False),
    "RD004": ("high", "deterministic", False),
    "RD005": ("critical", "deterministic", False),
    "GIS001": ("critical", "deterministic", False),
    "GIS002": ("critical", "deterministic", False),
    "GIS003": ("high", "deterministic", False),
    "GIS004": ("medium", "deterministic", False),
    "GIS005": ("medium", "deterministic", False),
}


def test_registry_covers_all_engine_rules():
    assert set(EXPECTED) <= {r.rule_id for r in all_rules()}


def test_registry_matches_engine_semantics():
    for rule_id, (sev, typ, review) in EXPECTED.items():
        rd = get_rule(rule_id)
        assert rd is not None, rule_id
        assert rd.baseline_severity == sev, rule_id
        assert rd.type == typ, rule_id
        assert rd.requires_human_review == review, rule_id


def test_only_heuristics_require_review():
    assert heuristic_rule_ids() == {"RD001", "RD002"}


def test_get_rule_definition_tool_shape():
    d = get_rule_definition("BLD001")
    assert d is not None
    assert d["rule_id"] == "BLD001"
    assert d["type"] == "deterministic"
    assert set(d) >= {"rule_id", "error_type", "name", "description",
                      "baseline_severity", "type", "requires_human_review",
                      "layer", "recommendation", "priority_hint"}


def test_get_rule_definition_unknown_returns_none():
    assert get_rule_definition("XXX999") is None
