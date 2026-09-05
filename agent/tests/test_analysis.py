"""End-to-end graph tests: heuristic classification, missing context,
batch runs, DB failures, malformed/lying LLM output."""
from __future__ import annotations

import json

import pytest

from agent.graph.builder import run_analysis
from agent.tests.conftest import (
    MISSING_RUN_ID,
    RUN_ID,
    StubLLM,
    build_memory_repo,
)


# ── template path (no LLM configured in CI) ─────────────────────────────────
def test_full_run_all_rules_template_path(repo, sample_analyses_expected):
    out = run_analysis(RUN_ID, repository=repo)
    assert out["results_loaded"] == 14
    assert len(out["analyses"]) == 14
    assert out["errors"] == []

    by_rule = {a["rule_id"]: a for a in out["analyses"]}
    assert set(by_rule) == set(sample_analyses_expected)
    for rule_id, (status, review, related) in sample_analyses_expected.items():
        a = by_rule[rule_id]
        assert a["status"] == status, rule_id
        assert a["human_review_required"] is review, rule_id
        assert a["related_features"] == related, rule_id
        assert a["severity"] != ""          # severity preserved from engine
    # Analyses were persisted
    assert len(repo.fetch_analyses(RUN_ID)) == 14


def test_severity_preserved_from_source(repo):
    out = run_analysis(RUN_ID, repository=repo)
    src = {r.result_id: r.severity for r in repo.fetch_results(RUN_ID)}
    for a in out["analyses"]:
        assert a["severity"] == src[a["result_id"]]


def test_bld001_explanation_is_grounded(repo):
    out = run_analysis(RUN_ID, repository=repo)
    a = next(x for x in out["analyses"] if x["rule_id"] == "BLD001")
    # echoes engine details (area value) but must not invent other numbers
    assert "34.52" in a["explanation"]
    assert "BLD_157" in a["explanation"]
    assert a["feature_id"] == "BLD_102"
    assert a["status"] == "confirmed"
    assert a["human_review_required"] is False


def test_heuristic_rows_are_candidates_and_persisted(repo):
    out = run_analysis(RUN_ID, repository=repo)
    cand = [a for a in out["analyses"] if a["status"] == "candidate"]
    assert {a["rule_id"] for a in cand} == {"RD001", "RD002"}
    for a in cand:
        assert a["human_review_required"] is True
        assert "candidate" in a["explanation"].lower() or "review" in a["explanation"].lower()


def test_missing_feature_context_returns_insufficient(repo):
    # Seed run with results whose features + details are absent.
    repo2 = build_memory_repo(results_file="missing_context_run.json",
                              run_id=MISSING_RUN_ID)
    out = run_analysis(MISSING_RUN_ID, repository=repo2)
    assert len(out["analyses"]) == 2
    by_rule = {a["rule_id"]: a for a in out["analyses"]}
    # Deterministic rule with no info -> insufficient_context
    assert by_rule["BLD002"]["status"] == "insufficient_context"
    assert by_rule["BLD002"]["insufficient_context"] is True
    # Heuristic rule with no info -> still a candidate (must be reviewed),
    # but explicitly flagged as having insufficient context to explain.
    assert by_rule["RD002"]["status"] == "candidate"
    assert by_rule["RD002"]["insufficient_context"] is True
    assert by_rule["RD002"]["human_review_required"] is True
    for a in out["analyses"]:
        assert "no details" in a["explanation"] or "not available" in a["explanation"]


def test_unknown_rule_is_informational(repo):
    from agent.core.models import ValidationResult
    from agent.db.memory import InMemoryRepository
    repo2 = InMemoryRepository(results=[
        ValidationResult(result_id=501, run_id=MISSING_RUN_ID, layer_name="roads",
                         feature_id="R_1", rule_id="ZZZ999", error_type="Mystery",
                         severity="high", details="something happened")])
    out = run_analysis(MISSING_RUN_ID, repository=repo2)
    assert out["analyses"][0]["status"] == "informational"
    assert out["analyses"][0]["human_review_required"] is False


def test_empty_run_summarizes_zero(empty_repo):
    out = run_analysis(RUN_ID, repository=empty_repo)
    assert out["results_loaded"] == 0
    assert out["analyses"] == []
    assert out["summary"]["total_errors"] == 0
    assert out["summary"]["critical_errors"] == 0


def test_summary_counts_and_priority(empty_repo, repo):
    out = run_analysis(RUN_ID, repository=repo)
    s = out["summary"]
    assert s["total_errors"] == 14
    assert s["critical_errors"] == 4   # BLD004, RD005, GIS001, GIS002
    assert s["high_errors"] == 6
    assert s["medium_errors"] == 4
    assert s["most_common_error"] in {  # several rules tied at 1 -> any is fine
        "Building Overlap", "Duplicate Buildings", "Invalid Geometry",
        "Missing Geometry", "Road Overshoot", "Road Undershoot",
        "Duplicate Roads", "Missing/Wrong CRS", "Invalid Coordinates",
        "Missing Required Attributes", "Wrong Data Type",
        "Invalid Attribute Values"}
    assert s["counts_by_rule"]["BLD001"] == 1
    assert s["counts_by_layer"]["roads"] == 5
    assert any("human review" in a.lower() for a in s["priority_actions"])
    assert any("critical" in a.lower() for a in s["priority_actions"])


# ── database failure handling ───────────────────────────────────────────────
class FailingRepo:
    """Repository that blows up on reads (simulated DB outage)."""

    def fetch_results(self, *a, **k):
        raise RuntimeError("connection refused")

    def fetch_related_features(self, *a, **k):
        raise RuntimeError("connection refused")

    def fetch_feature_context(self, *a, **k):
        raise RuntimeError("connection refused")

    def query_readonly(self, *a, **k):
        raise RuntimeError("connection refused")

    def save_analyses(self, analyses):
        return len(analyses)

    def fetch_analyses(self, run_id):
        return []

    def build_summary(self, results, analyses):
        from agent.db.base import Repository
        return Repository.build_summary(self, results, analyses)

    def priority_actions(self, summary):
        from agent.db.base import Repository
        return Repository.priority_actions(self, summary)


def test_db_failure_logged_not_fatal():
    out = run_analysis(RUN_ID, repository=FailingRepo())
    assert out["results_loaded"] == 0
    assert any("fetch_results" in e for e in out["errors"])
    assert out["summary"]["total_errors"] == 0


# ── LLM path robustness ─────────────────────────────────────────────────────
def test_llm_garbage_falls_back_to_template(repo):
    stub = StubLLM("this is not json {{{")
    out = run_analysis(RUN_ID, repository=repo, llm=stub)
    assert stub.calls >= 1
    assert len(out["analyses"]) == 14
    # template fallback still yields valid statuses
    by_rule = {a["rule_id"]: a for a in out["analyses"]}
    assert by_rule["RD001"]["status"] == "candidate"
    assert by_rule["BLD001"]["status"] == "confirmed"


def test_llm_retries_then_falls_back(repo):
    stub = StubLLM("nonsense", fail_attempts=3)
    out = run_analysis(RUN_ID, repository=repo, llm=stub)
    assert out["analyses"]  # non-empty despite persistent LLM failure


def test_llm_invents_result_id_is_dropped(repo):
    # LLM returns an entry for result 999999 that does not exist + valid ones.
    payload = json.dumps([{
        "result_id": 999999, "status": "confirmed",
        "explanation": "invented", "cause": None,
        "recommendation": None, "human_review_required": False,
        "related_features": []}])
    stub = StubLLM(payload)
    out = run_analysis(RUN_ID, repository=repo, llm=stub)
    # inventing a result_id must not crash; per-item template fallback fills gaps
    assert all(a["result_id"] in {r.result_id for r in repo.fetch_results(RUN_ID)}
               for a in out["analyses"])


def test_llm_cannot_downgrade_heuristic_to_confirmed(repo):
    payload = json.dumps([{
        "result_id": 5, "status": "confirmed",  # RD001 must stay candidate
        "explanation": "LLM tried to confirm it",
        "cause": None, "recommendation": None,
        "human_review_required": False, "related_features": []}])
    stub = StubLLM(payload)
    out = run_analysis(RUN_ID, repository=repo, llm=stub)
    a = next(x for x in out["analyses"] if x["rule_id"] == "RD001")
    assert a["status"] == "candidate"
    assert a["human_review_required"] is True


def test_llm_valid_analysis_is_used(repo):
    payload = json.dumps([{
        "result_id": 1, "status": "confirmed",
        "explanation": "BLD_102 and BLD_157 intersect; verified from engine details.",
        "cause": "positive-area intersection",
        "recommendation": "snap boundaries to touch only",
        "human_review_required": False,
        "related_features": ["BLD_157"]}])
    stub = StubLLM(payload)
    out = run_analysis(RUN_ID, repository=repo, llm=stub)
    a = next(x for x in out["analyses"] if x["result_id"] == 1)
    assert a["explanation"].startswith("BLD_102 and BLD_157")
    assert a["cause"] == "positive-area intersection"
    # items the LLM did not cover fall back to templates
    assert len(out["analyses"]) == 14


def test_multiple_errors_one_run_grouped(repo):
    out = run_analysis(RUN_ID, repository=repo)
    analyze_traces = [t for t in out["trace"] if t.startswith("[analyze]")]
    # group = distinct (layer, rule); sample_run has 14 distinct rules
    assert len(analyze_traces) == 14
    assert all("template" in t for t in analyze_traces)
