"""FastAPI router for the Error Analysis Agent.

Routes follow the team's FastAPI conventions (backend/ on origin/backend).
The backend teammate can mount this router:

    from agent.api.router import router as analysis_router
    app.include_router(analysis_router, prefix="/api")

or run the standalone app (agent.api.app:app) during development.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, UUID4

from agent.chat import answer_question
from agent.core.models import AnalyzeResponse, AnalysisListResponse, RunSummary
from agent.db.base import Repository
from agent.graph.builder import build_summary_model, run_analysis

router = APIRouter(tags=["validation-analysis"])


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    question: str
    answer: str
    sources: list[str] = Field(default_factory=list)


def get_repository() -> Repository:
    """FastAPI dependency: production repository (override in tests)."""
    from agent.db.postgres import PostgresRepository
    return PostgresRepository()


@router.post("/validation/{run_id}/analyze",
             response_model=AnalyzeResponse,
             summary="Trigger Error Analysis for a validation run")
def trigger_analysis(run_id: UUID4, repo: Repository = Depends(get_repository)):
    out = run_analysis(str(run_id), repository=repo)
    n = len(out.get("analyses", []))
    if out.get("errors"):
        # DB/context problems are logged and surfaced, not silently dropped.
        return AnalyzeResponse(
            run_id=str(run_id), status="completed_with_warnings",
            total_errors_analyzed=n,
            message="; ".join(out["errors"][:5]))
    return AnalyzeResponse(run_id=str(run_id), status="completed",
                           total_errors_analyzed=n,
                           message=f"Analyzed {n} validation error(s)")


@router.get("/validation/{run_id}/analysis",
            response_model=AnalysisListResponse,
            summary="Retrieve Error Analyses for a validation run")
def get_analysis(run_id: UUID4, repo: Repository = Depends(get_repository)):
    try:
        analyses = repo.fetch_analyses(str(run_id))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"analysis fetch failed: {exc}")
    if not analyses:
        raise HTTPException(
            status_code=404,
            detail="No agent analysis found for this run. "
                   "Call POST /api/validation/{run_id}/analyze first.")
    results = repo.fetch_results(str(run_id))
    summary = repo.build_summary(results, analyses)
    summary["priority_actions"] = repo.priority_actions(summary)
    return AnalysisListResponse(
        run_id=str(run_id),
        summary=build_summary_model(str(run_id), summary),
        analyses=analyses,
    )


@router.post("/validation/{run_id}/chat",
             response_model=ChatResponse,
             summary="Ask a grounded question about a run's engine results")
def chat_about_run(run_id: UUID4, body: ChatRequest,
                   repo: Repository = Depends(get_repository)):
    """Chat endpoint: answers from the run's stored analyses + summary only.

    Requires an LLM key (MEYAAR_LLM_API_KEY) — analysis endpoints work
    without one, chat does not.
    """
    try:
        out = answer_question(repo, str(run_id), body.question)
    except ValueError as exc:      # no analyses yet for this run
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        msg = str(exc)
        if "LLM key" in msg:
            raise HTTPException(status_code=503, detail=msg)
        raise HTTPException(status_code=502, detail=msg)
    return ChatResponse(**out)
