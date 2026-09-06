"""API endpoint tests (FastAPI TestClient with an in-memory repository)."""
from __future__ import annotations

import pytest

from agent.tests.conftest import RUN_ID, build_memory_repo


@pytest.fixture()
def client(repo, monkeypatch):
    """TestClient with backend auth/access-control stubbed out — these agent
    tests exercise agent logic, not the backend's login/teams feature."""
    import contextlib

    from fastapi.testclient import TestClient

    from agent.api import router as api_router
    from agent.api.app import app

    class _FakeEngine:
        def begin(self):
            return contextlib.nullcontext(None)

    app.dependency_overrides[api_router.get_repository] = lambda: repo
    app.dependency_overrides[api_router.current_user] = lambda: {
        "user_id": "00000000-0000-4000-8000-000000000001", "role": "admin"}
    monkeypatch.setattr(api_router, "database_engine", lambda: _FakeEngine())
    monkeypatch.setattr(api_router, "ensure_app_tables", lambda conn: None)
    monkeypatch.setattr(api_router, "require_run_access",
                        lambda conn, user, run_id: None)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_analyze_endpoint(client):
    resp = client.post(f"/api/validation/{RUN_ID}/analyze")
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == RUN_ID
    assert body["status"] == "completed"
    assert body["total_errors_analyzed"] == 14


def test_get_analysis_404_before_analyze(client):
    resp = client.get(f"/api/validation/{RUN_ID}/analysis")
    assert resp.status_code == 404


def test_get_analysis_after_analyze(client):
    client.post(f"/api/validation/{RUN_ID}/analyze")
    resp = client.get(f"/api/validation/{RUN_ID}/analysis")
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == RUN_ID
    assert body["summary"]["total_errors"] == 14
    assert body["summary"]["critical_errors"] == 4
    assert len(body["analyses"]) == 14
    rd = [a for a in body["analyses"] if a["rule_id"] == "RD001"][0]
    assert rd["status"] == "candidate"
    assert rd["human_review_required"] is True
    # executive narrative is written and returned with the summary
    assert body["summary"]["narrative"]
    assert "14 error" in body["summary"]["narrative"]
    # map-integration fields are present on every analysis
    for a in body["analyses"]:
        assert {"feature_id", "layer_name", "rule_id", "error_type",
                "severity"} <= set(a)


def test_get_remediation_after_analyze(client):
    client.post(f"/api/validation/{RUN_ID}/analyze")
    resp = client.get(f"/api/validation/{RUN_ID}/remediation")
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == RUN_ID
    recs = body["remediation"]
    assert len(recs) == 14
    by_id = {r["result_id"]: r for r in recs}
    # dashboard-distinguishable statuses
    assert by_id[3]["action"] == "auto_fix" and by_id[3]["status"] == "applied"
    assert by_id[5]["action"] == "human_review"
    assert by_id[5]["status"] == "pending_review"
    assert by_id[10]["action"] == "no_action" and by_id[10]["status"] == "none"


def test_get_remediation_404_before_analyze(client):
    resp = client.get(f"/api/validation/{RUN_ID}/remediation")
    # No records yet -> empty list (not an error): analyze creates them.
    assert resp.status_code == 200
    assert resp.json()["remediation"] == []


def test_analyze_empty_run(client, empty_repo):
    from agent.api import router as api_router
    from agent.api.app import app
    app.dependency_overrides[api_router.get_repository] = lambda: empty_repo
    resp = client.post(f"/api/validation/{RUN_ID}/analyze")
    body = resp.json()
    assert body["status"] == "completed"
    assert body["total_errors_analyzed"] == 0


def test_analyze_rejects_malformed_uuid(client):
    resp = client.post("/api/validation/not-a-uuid/analyze")
    assert resp.status_code == 422


def test_root_serves_chat_ui_and_info_route(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Meyaar" in r.text and "chat" in r.text.lower()
    i = client.get("/api/info")
    assert i.status_code == 200
    body = i.json()
    assert body["service"].startswith("Meyaar")
    assert "endpoints" in body and "llm" in body
    assert client.get("/health").status_code == 200
