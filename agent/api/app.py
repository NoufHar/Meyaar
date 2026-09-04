"""Standalone FastAPI app: serves the chat UI + the analysis/chat API.

Run:  uvicorn agent.api.app:app --reload
Open http://127.0.0.1:8000/ for the chat UI (or /docs for the API).
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from agent.api.router import router
from agent.core.config import settings
from agent.voice import available_engines

app = FastAPI(
    title="Meyaar Error Analysis Agent API",
    version="0.3.0",
    description="Agentic interpretation layer on top of the PostGIS rule engine.",
)
app.include_router(router, prefix="/api")

_UI_PATH = Path(__file__).resolve().parent / "static" / "index.html"


@app.get("/", include_in_schema=False)
def ui():
    """Simple chat UI for the agent."""
    return FileResponse(_UI_PATH, media_type="text/html")


@app.get("/api/info", include_in_schema=False)
def info():
    """Service/LLM info (JSON) for health checks and scripts."""
    return {
        "service": "Meyaar Error Analysis Agent API",
        "version": "0.3.0",
        "docs": "/docs",
        "health": "/health",
        "ui": "/",
        "endpoints": [
            "POST /api/validation/{run_id}/analyze",
            "GET  /api/validation/{run_id}/analysis",
            "POST /api/validation/{run_id}/chat",
        ],
        "llm": {
            "enabled": settings.llm_enabled,
            "model": settings.llm_model if settings.llm_enabled else "template-fallback",
        },
        "voice": available_engines(),
        "hint": "run_id is a UUID from public.validation_results (see CLI: python -m agent.cli analyze --help)",
    }


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}
