"""Shared fixtures: repositories seeded with realistic data + stub LLMs."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
RUN_ID = "8f0a1b2c-3d4e-4f5a-8b9c-0d1e2f3a4b5c"
MISSING_RUN_ID = "9a1b2c3d-4e5f-4a6b-8c7d-0e1f2a3b4c5d"


def _ctx(layer: str, fid: str, geom_type: str, srid: int = 4326) -> dict:
    return {
        "feature_id": fid,
        "layer_name": layer,
        "geometry_type": geom_type,
        "srid": srid,
        "centroid": "POINT(46.701 24.601)",
        "x_min": 46.700, "y_min": 24.600, "x_max": 46.702, "y_max": 24.602,
    }


def build_memory_repo(results_file: str = "sample_run.json", run_id: str = RUN_ID):
    from agent.core.models import ValidationResult
    from agent.db.memory import InMemoryRepository

    rows = json.loads((FIXTURES / results_file).read_text(encoding="utf-8"))
    rows = [r for r in rows if r["run_id"] == run_id]
    results = [ValidationResult(**r) for r in rows]
    repo = InMemoryRepository(results=results)
    # Feature store: present for most fixtures, deliberately ABSENT for the
    # ids used in missing_context_run.json (BLD_999 / RD_777).
    if run_id == RUN_ID:
        for layer, seeds in {
            "buildings": {
                "BLD_102": _ctx("buildings", "BLD_102", "Polygon"),
                "BLD_157": _ctx("buildings", "BLD_157", "Polygon"),
                "BLD_201": _ctx("buildings", "BLD_201", "Polygon"),
                "BLD_303": _ctx("buildings", "BLD_303", "Polygon"),
                "BLD_404": _ctx("buildings", "BLD_404", "Polygon"),
            },
            "roads": {
                "RD_101": _ctx("roads", "RD_101", "LineString"),
                "RD_102": _ctx("roads", "RD_102", "LineString"),
                "RD_103": _ctx("roads", "RD_103", "LineString"),
                "RD_104": _ctx("roads", "RD_104", "LineString"),
                "RD_105": _ctx("roads", "RD_105", "LineString"),
            },
        }.items():
            for fid, c in seeds.items():
                repo.seed_feature(layer, fid, c)
    return repo


@pytest.fixture()
def repo():
    return build_memory_repo()


@pytest.fixture()
def empty_repo():
    from agent.db.memory import InMemoryRepository
    return InMemoryRepository()


class StubLLM:
    """Configurable fake LLM for exercising the LLM path without a key."""

    def __init__(self, payload, fail_attempts: int = 0):
        self._payload = payload
        self._fail_attempts = fail_attempts
        self.calls = 0

    def invoke(self, prompt: str):
        self.calls += 1
        if self.calls <= self._fail_attempts:
            raise RuntimeError("simulated upstream failure")
        return type("R", (), {"content": self._payload})()


@pytest.fixture()
def sample_analyses_expected() -> dict:
    return {
        "BLD001": ("confirmed", False, ["BLD_157"]),
        "BLD002": ("confirmed", False, []),
        "BLD003": ("confirmed", False, []),
        "BLD004": ("confirmed", False, []),
        "RD001": ("candidate", True, []),
        "RD002": ("candidate", True, []),
        "RD003": ("confirmed", False, []),
        "RD004": ("confirmed", False, []),
        "RD005": ("confirmed", False, []),
        "GIS001": ("confirmed", False, []),
        "GIS002": ("confirmed", False, []),
        "GIS003": ("confirmed", False, []),
        "GIS004": ("confirmed", False, []),
        "GIS005": ("confirmed", False, []),
    }
