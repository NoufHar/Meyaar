"""LangGraph assembly + run entry point for the Error Analysis Agent.

    START -> load_results -+-> prepare -> analyze -> validate -> save -> summarize -> END
                           +---------------------------- (no results) -------> summarize -> END
"""
from __future__ import annotations

from typing import Optional

from agent.core.models import RunSummary
from agent.db.base import Repository


def build_graph():
    from langgraph.graph import END, START, StateGraph

    from agent.graph import nodes
    from agent.graph.state import AgentState

    g = StateGraph(AgentState)
    g.add_node("load", nodes.load_results)
    g.add_node("prepare", nodes.prepare_groups)
    g.add_node("analyze", nodes.analyze)
    g.add_node("validate", nodes.validate_output)
    g.add_node("save", nodes.save_analyses)
    g.add_node("summarize", nodes.summarize)

    g.add_edge(START, "load")
    g.add_conditional_edges(
        "load", nodes.route_after_load,
        {"prepare": "prepare", "summarize": "summarize"})
    g.add_edge("prepare", "analyze")
    g.add_edge("analyze", "validate")
    g.add_edge("validate", "save")
    g.add_edge("save", "summarize")
    g.add_edge("summarize", END)
    return g.compile()


def run_analysis(run_id: str, repository: Optional[Repository] = None,
                 llm: Optional[object] = None) -> dict:
    """Run the full Error Analysis workflow for a run.

    Args:
        run_id: UUID of a validation run in public.validation_results.
        repository: Repository instance (Postgres by default; inject
            InMemoryRepository for tests/offline demos).
        llm: optional ChatOpenAI; defaults to env-configured LLM or None.

    Returns a JSON-friendly dict {run_id, results_loaded, analyses, summary,
    trace, errors}. Also persists analyses to agent_error_analysis.
    """
    from agent.db.postgres import PostgresRepository

    repo = repository or PostgresRepository()
    config = {"configurable": {"repository": repo, "llm": llm}}
    app = build_graph()
    result = app.invoke({"run_id": run_id}, config)

    # LangGraph returns a dict-of-channels; our AgentState fields map 1:1.
    from agent.graph.state import AgentState
    from dataclasses import fields as dc_fields

    kwargs = {k: v for k, v in result.items()
              if k in {f.name for f in dc_fields(AgentState)}}
    final = AgentState(**kwargs)
    return final.to_result_dict()


def analyze_and_summarize(run_id: str, repository: Optional[Repository] = None,
                          llm: Optional[object] = None) -> dict:
    """Convenience wrapper: run_analysis + a typed RunSummary dict."""
    out = run_analysis(run_id, repository=repository, llm=llm)
    summary = out.get("summary") or {}
    return {
        "run_id": run_id,
        "status": "completed",
        "total_errors_analyzed": len(out.get("analyses", [])),
        "summary": summary,
        "errors": out.get("errors", []),
    }


def build_summary_model(run_id: str, summary: dict) -> RunSummary:
    return RunSummary(
        run_id=run_id,
        total_errors=summary.get("total_errors", 0),
        critical_errors=summary.get("critical_errors", 0),
        high_errors=summary.get("high_errors", 0),
        medium_errors=summary.get("medium_errors", 0),
        low_errors=summary.get("low_errors", 0),
        most_common_error=summary.get("most_common_error"),
        priority_actions=summary.get("priority_actions", []),
        counts_by_rule=summary.get("counts_by_rule", {}),
        counts_by_layer=summary.get("counts_by_layer", {}),
    )
