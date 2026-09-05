import pandas as pd
import pytest

from tools.vector_benchmark_evaluator import (
    build_feature_comparison,
    calculate_metrics,
    normalize_error_type,
)


def test_normalize_error_type():
    assert normalize_error_type(
        "Road Overshoot",
        "RD001",
    ) == "overshoot"

    assert normalize_error_type(
        "Road Undershoot",
        "RD002",
    ) == "undershoot"

    assert normalize_error_type(
        "Connectivity Error",
    ) == "connectivity_error"


def test_calculate_metrics():
    ground_truth = pd.DataFrame({
        "feature_id": [
            "road-1",
            "road-2",
            "road-3",
            "road-4",
            "road-5",
        ],
        "error_type": [
            "overshoot",
            "overshoot",
            "undershoot",
            "connectivity_error",
            "clean",
        ],
    })

    predictions = pd.DataFrame({
        "feature_id": [
            "road-1",
            "road-3",
            "road-6",
        ],
        "rule_id": [
            "RD001",
            "RD002",
            "RD001",
        ],
        "error_type": [
            "overshoot",
            "undershoot",
            "overshoot",
        ],
    })

    metrics = calculate_metrics(
        ground_truth,
        predictions,
    ).set_index("error_type")

    overshoot = metrics.loc["overshoot"]

    assert overshoot["true_positive"] == 1
    assert overshoot["false_positive"] == 1
    assert overshoot["false_negative"] == 1
    assert overshoot["precision"] == pytest.approx(
        0.5
    )
    assert overshoot["recall"] == pytest.approx(
        0.5
    )
    assert overshoot["f1"] == pytest.approx(
        0.5
    )

    undershoot = metrics.loc["undershoot"]

    assert undershoot["true_positive"] == 1
    assert undershoot["false_positive"] == 0
    assert undershoot["false_negative"] == 0
    assert undershoot["f1"] == pytest.approx(
        1.0
    )

    connectivity = metrics.loc[
        "connectivity_error"
    ]

    assert connectivity["true_positive"] == 0
    assert connectivity["predicted_count"] == 0
    assert connectivity["false_negative"] == 1
    assert connectivity["f1"] == pytest.approx(
        0.0
    )


def test_build_feature_comparison():
    ground_truth = pd.DataFrame({
        "feature_id": [
            "road-1",
            "road-2",
        ],
        "error_type": [
            "overshoot",
            "undershoot",
        ],
    })

    predictions = pd.DataFrame({
        "feature_id": [
            "road-1",
        ],
        "rule_id": [
            "RD001",
        ],
        "error_type": [
            "overshoot",
        ],
    })

    comparison = build_feature_comparison(
        ground_truth,
        predictions,
    ).set_index("feature_id")

    assert comparison.loc[
        "road-1",
        "correctly_detected",
    ]

    assert not comparison.loc[
        "road-2",
        "correctly_detected",
    ]

    assert comparison.loc[
        "road-2",
        "predicted_error_types",
    ] == "none"