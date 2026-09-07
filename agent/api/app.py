"""Standalone FastAPI app for the Error Analysis Agent (local development).

Run:  uvicorn agent.api.app:app --reload
Backend teammate can instead mount the router (see router.py docstring).

NOTE: on the project's main branch the agent router is mounted inside the
backend app (src/api/main.py) where every endpoint requires login + run
access. This standalone app is for LOCAL DEV: set MEYAAR_DEV_NO_AUTH=1 to
bypass that auth layer so you can click around the UI without accounts.
"""
from __future__ import annotations

import contextlib
import os
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


def _enable_dev_no_auth() -> None:
    """Local-dev bypass for the backend auth layer (see module docstring)."""
    from agent.api import router as r

    class _FakeEngine:
        def begin(self):
            return contextlib.nullcontext(None)

    app.dependency_overrides[r.current_user] = lambda: {
        "user_id": "00000000-0000-4000-8000-000000000001",
        "name": "dev", "role": "admin"}
    # Replace the access-check helpers with no-ops for local exploration.
    r.database_engine = lambda: _FakeEngine()          # noqa
    r.ensure_app_tables = lambda conn: None            # noqa
    r.require_run_access = lambda conn, user, run_id: None  # noqa


if os.getenv("MEYAAR_DEV_NO_AUTH", "").strip().lower() in {"1", "true", "yes"}:
    _enable_dev_no_auth()


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
            "GET  /api/validation/{run_id}/remediation",
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
