"""Remediation tests (trainer Part 11) — graph integration + policy unit tests.

Covers the required scenarios:
  1. invalid building geometry  -> measurements available -> auto-fix applied
  2. RD001 road overshoot       -> heuristic -> human review (auto rejected)
  3. RD002 road undershoot      -> human review
  4. missing geometry           -> no invention -> human review
  5. LLM invalid action         -> deterministic validator rejects it
  6. LLM claims heuristic safe  -> system overrides -> human review
  7. remediation SQL fails      -> failure recorded (rollback)
  8. LLM disabled               -> template path still remediates deterministically
  9. no validation errors       -> clean run: load -> summarize (no remediation)

Sample run mapping (see tests/fixtures/sample_run.json):
  result 3 = BLD003 invalid geometry (buildings, feature BLD_303)
  result 4 = BLD004 missing geometry (buildings, feature BLD_404)
  result 5 = RD001 overshoot (roads, feature RD_101)
  result 6 = RD002 undershoot (roads, feature RD_102)
  result 8 = RD004 invalid geometry (roads, feature RD_104)
  result 9 = RD005 missing geometry (roads, feature RD_105)
"""
from __future__ import annotations

import json

import pytest

from agent.core.models import ErrorAnalysis, ValidationResult
from agent.db.memory import InMemoryRepository
from agent.graph.builder import run_analysis
from agent.remediation.service import decide
from agent.rules.registry import get_rule
from agent.tests.conftest import RUN_ID, StubLLM, build_memory_repo


def _recs(out: dict) -> dict[int, dict]:
    return {r["result_id"]: r for r in out["remediation"]}


def _result(repo, result_id: int) -> ValidationResult:
    return next(r for r in repo.fetch_results(RUN_ID) if r.result_id == result_id)


# ── scenario 1: safe deterministic auto-fix ─────────────────────────────────
def test_invalid_building_geometry_is_auto_fixed(repo):
    out = run_analysis(RUN_ID, repository=repo)
    rec = _recs(out)[3]                      # BLD003, feature BLD_303
    assert rec["action"] == "auto_fix"
    assert rec["remediation_type"] == "geometry_repair"
    assert rec["status"] == "applied"
    assert rec["before_state"].get("is_valid") is False
    assert rec["after_state"].get("is_valid") is True
    assert rec["human_review_required"] is False
    # The repository really performed the repair (in-memory double).
    assert ("buildings", "BLD_303") in repo.repaired_features
    # Measurement context is available for the same feature (Part 1 seam).
    m = repo.fetch_spatial_measurements("buildings", ["BLD_303"])
    assert m["BLD_303"]["geometry_type"] == "Polygon"
    assert m["BLD_303"]["bbox"] is not None


def test_road_invalid_geometry_also_auto_fixed(repo):
    out = run_analysis(RUN_ID, repository=repo)
    rec = _recs(out)[8]                      # RD004, feature RD_104
    assert rec["action"] == "auto_fix" and rec["status"] == "applied"
    assert ("roads", "RD_104") in repo.repaired_features


# ── scenarios 2 + 3: heuristic topology → human review ──────────────────────
@pytest.mark.parametrize("result_id,rule_id,feature", [
    (5, "RD001", "RD_101"),   # road overshoot
    (6, "RD002", "RD_102"),   # road undershoot
])
def test_heuristic_topology_escalated_to_human_review(repo, result_id, rule_id, feature):
    out = run_analysis(RUN_ID, repository=repo)
    rec = _recs(out)[result_id]
    assert rec["rule_id"] == rule_id
    assert rec["feature_id"] == feature
    assert rec["action"] == "human_review"
    assert rec["status"] == "pending_review"
    assert rec["human_review_required"] is True
    assert rec["remediation_type"] == "human_review"
    assert "heuristic" in rec["reason"].lower() or "registry" in rec["reason"].lower()
    assert rec["recommended_action"]           # guidance for the reviewer


# ── scenario 4: missing geometry → no invention ─────────────────────────────
@pytest.mark.parametrize("result_id,rule_id", [(4, "BLD004"), (9, "RD005")])
def test_missing_geometry_never_invented(repo, result_id, rule_id):
    out = run_analysis(RUN_ID, repository=repo)
    rec = _recs(out)[result_id]
    assert rec["rule_id"] == rule_id
    assert rec["action"] == "human_review"     # supply geometry at source
    assert rec["status"] == "pending_review"
    assert rec["before_state"] == {}           # nothing was invented/changed
    assert rec["after_state"] == {}


# ── scenarios 5 + 6: LLM cannot override policy (unit level) ────────────────
def _rule_dict(rule_id: str) -> dict:
    return get_rule(rule_id).model_dump()


def _analysis(result: ValidationResult, status: str = "confirmed") -> ErrorAnalysis:
    return ErrorAnalysis(
        result_id=result.result_id, run_id=result.run_id,
        layer_name=result.layer_name, feature_id=result.feature_id,
        rule_id=result.rule_id, error_type=result.error_type,
        severity=result.severity, status=status,
        explanation="test", agent_model="template-fallback")


def test_llm_invalid_remediation_action_rejected(repo):
    r = _result(repo, 3)                       # BLD003 (auto-allowed rule)
    d = decide(r, _analysis(r), _rule_dict("BLD003"),
               llm_intent={"action": "DROP TABLE buildings", "reason": "nope"},
               feature_available=True)
    assert d.action == "auto_fix"              # policy outcome wins
    assert "invalid remediation action" in d.reason
    # An invalid suggestion must also be harmless on a human-review rule.
    r5 = _result(repo, 5)
    d5 = decide(r5, _analysis(r5, status="candidate"), _rule_dict("RD001"),
                llm_intent={"action": "explode everything"})
    assert d5.action == "human_review"
    assert "invalid remediation action" in d5.reason


def test_llm_cannot_autofix_heuristic_rule(repo):
    r = _result(repo, 5)                       # RD001 overshoot
    d = decide(r, _analysis(r, status="candidate"), _rule_dict("RD001"),
               llm_intent={"action": "auto_fix", "reason": "looks safe to me"})
    assert d.action == "human_review"          # system overrides the LLM
    assert d.human_review_required is True
    assert "cannot override" in d.reason


def test_llm_cannot_autofix_when_registry_forbids(repo):
    r = _result(repo, 1)                       # BLD001 overlap (auto not allowed)
    d = decide(r, _analysis(r), _rule_dict("BLD001"),
               llm_intent={"action": "auto_fix"})
    assert d.action == "human_review"
    assert "cannot override" in d.reason


def test_llm_cannot_autofix_when_feature_missing(repo):
    r = _result(repo, 8)                       # RD004 auto-allowed rule
    d = decide(r, _analysis(r), _rule_dict("RD004"),
               llm_intent={"action": "auto_fix"}, feature_available=False)
    assert d.action == "human_review"          # refuse blind mutation
    assert "could not be located" in d.reason


# ── scenario 6 (integration): lying LLM through the graph ───────────────────
def test_llm_autofix_claim_on_heuristic_overridden_in_graph(repo):
    payload = json.dumps([{
        "result_id": 5, "status": "confirmed",   # LLM lies: RD001 "confirmed"
        "explanation": "LLM thinks it is safe",
        "cause": None, "recommendation": "trim it",
        "human_review_required": False, "related_features": [],
        "remediation_intent": {"action": "auto_fix", "reason": "safe"}}])
    out = run_analysis(RUN_ID, repository=repo, llm=StubLLM(payload))
    rec = _recs(out)[5]
    assert rec["action"] == "human_review"      # policy overrode the LLM
    assert rec["status"] == "pending_review"
    assert "cannot override" in rec["reason"] or "override" in rec["reason"]


# ── scenario 7: SQL failure recorded (transaction rollback simulated) ───────
def test_remediation_sql_failure_recorded_and_others_continue():
    repo = build_memory_repo()
    # Make RD_104's repair blow up; BLD_303 stays healthy.
    ctx = repo.fetch_feature_context("roads", "RD_104") or {}
    ctx = dict(ctx, repair_fails=True)
    repo.seed_feature("roads", "RD_104", ctx)

    out = run_analysis(RUN_ID, repository=repo)
    rec = _recs(out)[8]                        # RD004 -> failed
    assert rec["action"] == "auto_fix"
    assert rec["status"] == "failed"
    assert "rolled back" in rec["reason"]
    assert any("remediation.RD004" in e for e in out["errors"])
    # The other auto-fix still succeeded; run did not crash.
    assert _recs(out)[3]["status"] == "applied"
    assert ("buildings", "BLD_303") in repo.repaired_features
    assert ("roads", "RD_104") not in repo.repaired_features


def test_auto_fix_refused_when_feature_absent_in_graph(repo):
    # Drop RD_104 from the feature store: policy-approved but unlocatable.
    del repo._features["roads"]["RD_104"]      # noqa: SLF001 (test double)
    out = run_analysis(RUN_ID, repository=repo)
    rec = _recs(out)[8]
    assert rec["action"] == "human_review"
    assert "could not be located" in rec["reason"]


# ── scenario 8: LLM disabled → deterministic remediation still happens ──────
def test_template_path_remediation_is_deterministic(repo):
    out = run_analysis(RUN_ID, repository=repo)          # no LLM (CI)
    assert len(out["remediation"]) == 14
    by_id = _recs(out)
    # Exact policy mapping for the 14-row fixture run.
    assert by_id[3]["action"] == "auto_fix" and by_id[3]["status"] == "applied"
    assert by_id[8]["action"] == "auto_fix" and by_id[8]["status"] == "applied"
    for rid in (1, 2, 4, 5, 6, 7, 9):
        assert by_id[rid]["action"] == "human_review", rid
        assert by_id[rid]["status"] == "pending_review", rid
    for rid in range(10, 15):                              # GIS, no feature row
        assert by_id[rid]["action"] == "no_action", rid
        assert by_id[rid]["status"] == "none", rid
    # Every analysis got exactly one audit record, persisted.
    assert len(repo.fetch_remediation_records(RUN_ID)) == 14
    assert all(r["agent_model"] == "template-fallback"
               for r in out["remediation"])


# ── scenario 9: clean run keeps load -> summarize, no remediation ───────────
def test_clean_run_no_remediation(empty_repo):
    out = run_analysis(RUN_ID, repository=empty_repo)
    assert out["results_loaded"] == 0
    assert out["analyses"] == []
    assert out["remediation"] == []
    assert out["summary"]["total_errors"] == 0
    assert not any("[remediate]" in t for t in out["trace"])


# ── records are idempotent on re-run ────────────────────────────────────────
def test_rerun_remediation_is_idempotent(repo):
    run_analysis(RUN_ID, repository=repo)
    out2 = run_analysis(RUN_ID, repository=repo)
    records = repo.fetch_remediation_records(RUN_ID)
    assert len(records) == 14
    assert out2["remediation"][0]["result_id"] == 1
    assert len({(r["run_id"], r["result_id"]) for r in records}) == 14
