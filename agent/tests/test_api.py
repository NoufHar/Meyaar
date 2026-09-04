"""API endpoint tests (FastAPI TestClient with an in-memory repository)."""
from __future__ import annotations

import pytest

from agent.tests.conftest import RUN_ID, build_memory_repo


@pytest.fixture()
def client(repo):
    from fastapi.testclient import TestClient

    from agent.api.app import app
    from agent.api import router as api_router

    app.dependency_overrides[api_router.get_repository] = lambda: repo
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
    # map-integration fields are present on every analysis
    for a in body["analyses"]:
        assert {"feature_id", "layer_name", "rule_id", "error_type",
                "severity"} <= set(a)


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
