"""Chat-layer tests: grounding, source filtering, no-LLM behaviour."""
from __future__ import annotations

import json

import pytest

from agent.chat import answer_question, build_chat_context
from agent.graph.builder import run_analysis
from agent.tests.conftest import RUN_ID, StubLLM, build_memory_repo


def _seed(repo) -> None:
    # Chat reads STORED analyses, so analyze the run first (template path).
    run_analysis(RUN_ID, repository=repo)


def test_context_contains_summary_and_analyses(repo):
    _seed(repo)
    ctx = build_chat_context(repo, RUN_ID)
    assert ctx["run_id"] == RUN_ID
    assert ctx["summary"]["total_errors"] == 14
    assert len(ctx["analyses"]) == 14
    assert ctx["rules"]["RD001"]["type"] == "heuristic"


def test_context_contains_remediation_audit(repo):
    _seed(repo)   # run_analysis also persists remediation records
    ctx = build_chat_context(repo, RUN_ID)
    rem = ctx["remediation"]
    assert rem["available"] is True
    # 14 records: BLD003+RD004 applied, RD001/RD002+others pending_review,
    # GIS001-005 no_action (layer-level), none failed in the fixture run.
    assert rem["summary"]["total"] == 14
    assert rem["summary"]["auto_fixed"] == 2
    assert rem["summary"]["failed"] == 0
    assert rem["summary"]["pending_review"] == 7
    assert rem["summary"]["no_action"] == 5
    assert len(rem["items"]) == 14
    item = rem["items"][0]
    assert {"rule_id", "feature_id", "action", "status",
            "remediation_type"} <= set(item)


def test_chat_prompt_includes_remediation_audit(repo):
    _seed(repo)
    prompts: list[str] = []

    class RecordingLLM:
        def invoke(self, prompt):
            prompts.append(prompt)
            return type("R", (), {"content": json.dumps({
                "answer": "Two invalid geometries were repaired automatically; "
                          "the rest are queued for human review.",
                "sources": []})})()

    out = answer_question(repo, RUN_ID, "what was fixed automatically?", llm=RecordingLLM())
    assert "remediated automatically" in out["answer"] or "repaired automatically" in out["answer"]
    joined = prompts[0]
    assert '"remediation"' in joined
    assert '"auto_fixed": 2' in joined
    assert '"pending_review": 7' in joined


def test_chat_works_when_remediation_table_missing(repo):
    _seed(repo)
    original = repo.fetch_remediation_records

    def boom(run_id):
        raise RuntimeError("relation agent_remediation_actions does not exist")

    repo.fetch_remediation_records = boom
    try:
        ctx = build_chat_context(repo, RUN_ID)
        assert ctx["remediation"]["available"] is False
        assert ctx["remediation"]["items"] == []
        # And answering still works (analysis grounding unaffected).
        stub = StubLLM(json.dumps({"answer": "ok", "sources": ["RD005"]}))
        out = answer_question(repo, RUN_ID, "hi", llm=stub)
        assert out["answer"] == "ok"
    finally:
        repo.fetch_remediation_records = original


def test_answer_returns_question_answer_sources(repo):
    _seed(repo)
    stub = StubLLM(json.dumps({
        "answer": "Fix critical missing geometry first (RD005, BLD004).",
        "sources": ["RD005", "BLD004", "FAKE@nothing"]}))   # fake must be dropped
    out = answer_question(repo, RUN_ID, "what should I fix first?", llm=stub)
    assert out["question"] == "what should I fix first?"
    assert out["answer"].startswith("Fix critical")
    assert set(out["sources"]) == {"RD005", "BLD004"}   # FAKE@nothing filtered out


def test_sources_are_only_known_ids(repo):
    _seed(repo)
    stub = StubLLM(json.dumps({
        "answer": "answer",
        "sources": ["BLD001@BLD_102", "BLD_102", "GHOST_9", "BLD001"]}))
    out = answer_question(repo, RUN_ID, "q", llm=stub)
    assert "BLD001@BLD_102" in out["sources"]
    assert "BLD_102" in out["sources"]
    assert "BLD001" in out["sources"]
    assert "GHOST_9" not in out["sources"]   # hallucinated id dropped


def test_chat_without_analyses_raises(empty_repo):
    with pytest.raises(ValueError, match="No agent analysis"):
        build_chat_context(empty_repo, RUN_ID)


def test_chat_requires_llm(repo, monkeypatch):
    _seed(repo)
    import agent.chat as chat_mod
    monkeypatch.setattr(chat_mod, "get_llm", lambda: None)
    with pytest.raises(RuntimeError, match="LLM key"):
        answer_question(repo, RUN_ID, "hi", llm=None)


def test_malformed_llm_answer_raises(repo):
    _seed(repo)
    stub = StubLLM("not json at all")
    with pytest.raises(RuntimeError, match="did not return a valid answer"):
        answer_question(repo, RUN_ID, "hi", llm=stub)
