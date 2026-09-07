"""Tests for the spatial-measurements tool (Part 1) and the remediation
policy fields added to the rule registry (Part 4)."""
from __future__ import annotations

import pytest

from agent.db.memory import InMemoryRepository
from agent.rules.registry import all_rules, get_rule
from agent.tools import get_spatial_measurements


def _polygon_repo():
    repo = InMemoryRepository()
    repo.seed_feature("buildings", "BLD_157", {
        "feature_id": "BLD_157", "layer_name": "buildings",
        "geometry_type": "Polygon", "srid": 4326,
        "area_m2": 248.7, "vertex_count": 32, "is_valid": True,
        "centroid": "POINT(46.701 24.601)",
        "x_min": 46.700, "y_min": 24.600, "x_max": 46.702, "y_max": 24.602,
    })
    repo.seed_feature("buildings", "BLD_102", {
        "feature_id": "BLD_102", "layer_name": "buildings",
        "geometry_type": "Polygon", "srid": 4326,
        "centroid": "POINT(46.700 24.600)",
        "x_min": 46.699, "y_min": 24.599, "x_max": 46.701, "y_max": 24.601,
    })
    repo.seed_feature("roads", "RD_101", {
        "feature_id": "RD_101", "layer_name": "roads",
        "geometry_type": "LineString", "srid": 4326,
        "length_m": 125.4, "vertex_count": 14,
        "centroid": "POINT(46.68 24.66)",
        "x_min": 46.670, "y_min": 24.650, "x_max": 46.690, "y_max": 24.670,
    })
    return repo


# ── Part 1: measurements tool ───────────────────────────────────────────────
def test_polygon_measurements_shape_and_values():
    repo = _polygon_repo()
    m = get_spatial_measurements(repo, "buildings", "BLD_157")
    assert m is not None
    assert m["feature_id"] == "BLD_157"
    assert m["geometry_type"] == "Polygon"
    assert m["srid"] == 4326
    assert m["area_m2"] == 248.7        # seeded from PostGIS-computed value
    assert m["length_m"] is None        # a polygon has no meaningful length
    assert m["vertex_count"] == 32
    assert m["bbox"] == [46.700, 24.600, 46.702, 24.602]
    assert m["centroid"] == "POINT(46.701 24.601)"


def test_linestring_measurements_no_area():
    repo = _polygon_repo()
    m = get_spatial_measurements(repo, "roads", "RD_101")
    assert m is not None
    assert m["geometry_type"] == "LineString"
    assert m["length_m"] == 125.4
    assert m["area_m2"] is None         # never invented for a line


def test_relationship_measurements_block():
    repo = _polygon_repo()
    # Seed an overlap relationship on BLD_102 (context carries values the
    # real PostGIS implementation computes live).
    m = get_spatial_measurements(repo, "buildings", "BLD_102",
                                 other_feature_id="BLD_157")
    assert m is not None
    assert m["other_feature_id"] == "BLD_157"
    assert "distance_m" in m and "intersects" in m and "overlap_area_m2" in m
    assert m["overlap_area_m2"] is None or isinstance(m["overlap_area_m2"], float)


def test_measurements_missing_feature_returns_none():
    repo = _polygon_repo()
    assert get_spatial_measurements(repo, "buildings", "BLD_GHOST") is None
    assert get_spatial_measurements(repo, "roads", "RD_GHOST") is None


def test_measurements_reuse_repository_not_raw_connections():
    """The tool must go through the Repository interface (never open its own
    connection): calling it on the in-memory repo proves the seam."""
    repo = _polygon_repo()
    m = get_spatial_measurements(repo, "buildings", "BLD_157")
    assert m and m["geometry_type"] == "Polygon"


# ── Part 4: registry remediation policy ─────────────────────────────────────
EXPECTED_POLICY = {
    # rule -> (remediation_type, auto_fix_allowed)
    "BLD001": ("human_review", False),
    "BLD002": ("human_review", False),
    "BLD003": ("geometry_repair", True),
    "BLD004": ("human_review", False),
    "RD001":  ("human_review", False),
    "RD002":  ("human_review", False),
    "RD003":  ("human_review", False),
    "RD004":  ("geometry_repair", True),
    "RD005":  ("human_review", False),
    "GIS001": ("crs_transform", False),
    "GIS002": ("human_review", False),
    "GIS003": ("attribute_correction", False),
    "GIS004": ("attribute_correction", False),
    "GIS005": ("attribute_correction", False),
}


def test_registry_declares_remediation_policy_for_all_rules():
    registered = {r.rule_id for r in all_rules()}
    assert set(EXPECTED_POLICY) == registered
    for rule_id, (rtype, auto) in EXPECTED_POLICY.items():
        rd = get_rule(rule_id)
        assert rd.remediation_type == rtype, rule_id
        assert rd.auto_fix_allowed is auto, rule_id
        assert rd.remediation_description, rule_id   # human-readable policy


def test_only_invalid_geometry_rules_allow_autofix():
    auto = {r.rule_id for r in all_rules() if r.auto_fix_allowed}
    assert auto == {"BLD003", "RD004"}


def test_heuristics_never_autofix():
    rd001 = get_rule("RD001")
    rd002 = get_rule("RD002")
    assert rd001.type == "heuristic" and not rd001.auto_fix_allowed
    assert rd002.type == "heuristic" and not rd002.auto_fix_allowed
    assert rd001.requires_human_review and rd002.requires_human_review
