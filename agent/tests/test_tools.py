"""Tool + SQL-guard tests."""
from __future__ import annotations

import pytest

from agent.db.memory import InMemoryRepository
from agent.tools import (
    get_feature_context,
    get_related_features,
    get_validation_results,
    query_postgis,
)
from agent.tools.sql_guard import assert_readonly_sql

RUN_ID = "8f0a1b2c-3d4e-4f5a-8b9c-0d1e2f3a4b5c"


def _repo():
    return InMemoryRepository()


# ── SQL guard ───────────────────────────────────────────────────────────────
@pytest.mark.parametrize("sql", [
    "SELECT * FROM public.validation_results",
    "SELECT rule_id, count(*) FROM public.validation_results GROUP BY rule_id",
    "WITH recent AS (SELECT run_id FROM public.validation_results) SELECT * FROM recent",
    "EXPLAIN SELECT * FROM public.roads",
    "SELECT 'update roads set geometry=null' AS note",          # keyword inside literal
    "SELECT 'DROP TABLE validation_results' AS note",           # literal spoof attempt
])
def test_guard_accepts_readonly(sql):
    assert_readonly_sql(sql)  # must not raise


@pytest.mark.parametrize("sql", [
    "UPDATE public.roads SET geometry = NULL",
    "DELETE FROM public.validation_results",
    "DROP TABLE public.buildings",
    "INSERT INTO public.roads VALUES (1)",
    "TRUNCATE public.roads",
    "ALTER TABLE public.roads ADD COLUMN x int",
    "CREATE TABLE evil AS SELECT 1",
    "GRANT ALL ON public.roads TO public",
    "SELECT * INTO scratch FROM public.roads",
    "SELECT 1; DROP TABLE public.roads",                        # multi-statement
    "SELECT 1; -- trailing comment is fine but semicolon above is not",
])
def test_guard_rejects_writes(sql):
    with pytest.raises(ValueError):
        assert_readonly_sql(sql)


def test_guard_rejects_empty():
    with pytest.raises(ValueError):
        assert_readonly_sql("   ")
    with pytest.raises(ValueError):
        assert_readonly_sql("")


# ── tools against the in-memory repo ────────────────────────────────────────
def test_tool_registry_exposes_required_tools():
    from agent.tools import TOOL_REGISTRY, tool_descriptions

    assert set(TOOL_REGISTRY) == {
        "get_validation_results", "get_feature_context", "get_related_features",
        "query_postgis_readonly", "get_rule_definition"}
    names = [d["name"] for d in tool_descriptions()]
    assert names == ["get_validation_results", "get_feature_context",
                     "get_related_features", "query_postgis_readonly",
                     "get_rule_definition"]


def test_query_postgis_readonly_alias_shares_guard():
    from agent.tools import query_postgis_readonly
    with pytest.raises(ValueError):
        query_postgis_readonly(_repo(), "DROP TABLE public.roads")


def test_query_postgis_rejects_write_on_repo():
    with pytest.raises(ValueError):
        query_postgis(_repo(), "DELETE FROM public.validation_results")


def test_get_validation_results_filters():
    from agent.core.models import ValidationResult
    base = ValidationResult(result_id=1, run_id=RUN_ID, layer_name="buildings",
                            feature_id="BLD_1", rule_id="BLD001",
                            error_type="Building Overlap", severity="high", details="x")
    repo = InMemoryRepository(results=[base])
    assert len(get_validation_results(repo, RUN_ID)) == 1
    assert get_validation_results(repo, RUN_ID, rule_id="RD001") == []
    assert len(get_validation_results(repo, RUN_ID, severity="high")) == 1
    assert len(get_validation_results(repo, RUN_ID, rule_id="BLD001",
                                      layer_name="buildings")) == 1


def test_get_feature_context_missing_returns_none():
    repo = _repo()
    assert get_feature_context(repo, "buildings", "BLD_NOPE") is None


def test_get_feature_context_found():
    repo = _repo()
    repo.seed_feature("buildings", "BLD_1",
                      {"feature_id": "BLD_1", "geometry_type": "Polygon", "srid": 4326})
    ctx = get_feature_context(repo, "buildings", "BLD_1")
    assert ctx is not None
    assert ctx["geometry_type"] == "Polygon"


def test_get_related_features_missing_absent():
    repo = _repo()
    repo.seed_feature("buildings", "BLD_A", {"feature_id": "BLD_A"})
    out = get_related_features(repo, "buildings", ["BLD_A", "BLD_GHOST"])
    assert set(out) == {"BLD_A"}
