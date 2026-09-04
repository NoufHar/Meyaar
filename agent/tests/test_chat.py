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
