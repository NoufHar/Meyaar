import argparse
import json
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


load_dotenv()


TARGET_ERROR_TYPES = (
    "overshoot",
    "undershoot",
    "connectivity_error",
)


RULE_TYPE_MAP = {
    "RD001": "overshoot",
    "RD002": "undershoot",
}


def normalize_error_type(
    error_type: str,
    rule_id: str | None = None,
) -> str:
    if rule_id in RULE_TYPE_MAP:
        return RULE_TYPE_MAP[rule_id]

    value = str(error_type).strip().lower()

    replacements = {
        "road overshoot": "overshoot",
        "road undershoot": "undershoot",
        "connectivity error": "connectivity_error",
        "road connectivity error": "connectivity_error",
        "connectivity_error": "connectivity_error",
    }

    return replacements.get(
        value,
        value.replace(" ", "_"),
    )


def load_ground_truth(
    ground_truth_path: str | Path,
) -> pd.DataFrame:
    frame = pd.read_csv(ground_truth_path)

    required_columns = {
        "id",
        "error_type",
    }

    missing_columns = (
        required_columns - set(frame.columns)
    )

    if missing_columns:
        raise ValueError(
            "Ground truth is missing columns: "
            + ", ".join(sorted(missing_columns))
        )

    result = frame[
        ["id", "error_type"]
    ].copy()

    result = result.rename(
        columns={"id": "feature_id"}
    )

    result["feature_id"] = (
        result["feature_id"].astype(str)
    )

    result["error_type"] = result[
        "error_type"
    ].apply(normalize_error_type)

    return result


def load_predictions(
    database_url: str,
    run_id: str,
) -> pd.DataFrame:
    engine = create_engine(
        database_url,
        pool_pre_ping=True,
    )

    query = text(
        """
        SELECT
            feature_id,
            rule_id,
            error_type
        FROM public.validation_results
        WHERE run_id = :run_id
        ORDER BY result_id
        """
    )

    try:
        with engine.connect() as connection:
            rows = connection.execute(
                query,
                {"run_id": run_id},
            ).mappings().all()
    finally:
        engine.dispose()

    frame = pd.DataFrame(rows)

    if frame.empty:
        return pd.DataFrame(
            columns=[
                "feature_id",
                "rule_id",
                "error_type",
            ]
        )

    frame["feature_id"] = (
        frame["feature_id"].astype(str)
    )

    frame["error_type"] = frame.apply(
        lambda row: normalize_error_type(
            row["error_type"],
            row["rule_id"],
        ),
        axis=1,
    )

    return frame


def calculate_metrics(
    ground_truth: pd.DataFrame,
    predictions: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for error_type in TARGET_ERROR_TYPES:
        actual_ids = set(
            ground_truth.loc[
                ground_truth["error_type"]
                == error_type,
                "feature_id",
            ]
        )

        predicted_ids = set(
            predictions.loc[
                predictions["error_type"]
                == error_type,
                "feature_id",
            ]
        )

        true_positive = len(
            actual_ids & predicted_ids
        )

        false_positive = len(
            predicted_ids - actual_ids
        )

        false_negative = len(
            actual_ids - predicted_ids
        )

        precision = (
            true_positive
            / (true_positive + false_positive)
            if true_positive + false_positive
            else 0.0
        )

        recall = (
            true_positive
            / (true_positive + false_negative)
            if true_positive + false_negative
            else 0.0
        )

        f1 = (
            2 * precision * recall
            / (precision + recall)
            if precision + recall
            else 0.0
        )

        rows.append({
            "error_type": error_type,
            "ground_truth_count": len(
                actual_ids
            ),
            "predicted_count": len(
                predicted_ids
            ),
            "true_positive": true_positive,
            "false_positive": false_positive,
            "false_negative": false_negative,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        })

    return pd.DataFrame(rows)


def build_feature_comparison(
    ground_truth: pd.DataFrame,
    predictions: pd.DataFrame,
) -> pd.DataFrame:
    actual = ground_truth.rename(
        columns={
            "error_type": "actual_error_type"
        }
    )

    detected = (
        predictions.groupby("feature_id")[
            "error_type"
        ]
        .apply(
            lambda values: ",".join(
                sorted(set(values))
            )
        )
        .rename("predicted_error_types")
        .reset_index()
    )

    comparison = actual.merge(
        detected,
        on="feature_id",
        how="left",
    )

    comparison[
        "predicted_error_types"
    ] = comparison[
        "predicted_error_types"
    ].fillna("none")

    comparison["correctly_detected"] = (
        comparison.apply(
            lambda row: (
                row["actual_error_type"]
                in row[
                    "predicted_error_types"
                ].split(",")
            ),
            axis=1,
        )
    )

    return comparison


def run_evaluation(
    ground_truth_path: str | Path,
    database_url: str,
    run_id: str,
    output_directory: str | Path,
) -> pd.DataFrame:
    ground_truth = load_ground_truth(
        ground_truth_path
    )

    predictions = load_predictions(
        database_url,
        run_id,
    )

    metrics = calculate_metrics(
        ground_truth,
        predictions,
    )

    comparison = build_feature_comparison(
        ground_truth,
        predictions,
    )

    output_path = Path(output_directory)
    output_path.mkdir(
        parents=True,
        exist_ok=True,
    )

    metrics.to_csv(
        output_path / "vector_metrics.csv",
        index=False,
    )

    comparison.to_csv(
        output_path / "feature_comparison.csv",
        index=False,
    )

    report = {
        "run_id": run_id,
        "ground_truth_rows": len(
            ground_truth
        ),
        "prediction_rows": len(
            predictions
        ),
        "metrics": metrics.to_dict(
            orient="records"
        ),
    }

    with (
        output_path / "vector_metrics.json"
    ).open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            report,
            file,
            indent=2,
        )

    return metrics


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate Meyaar vector validation "
            "against benchmark ground truth."
        )
    )

    parser.add_argument(
        "--ground-truth",
        required=True,
    )

    parser.add_argument(
        "--run-id",
        required=True,
    )

    parser.add_argument(
        "--database-url",
        default=os.getenv(
            "MEYAAR_DATABASE_URL"
        ),
    )

    parser.add_argument(
        "--output-directory",
        default="outputs/vector_benchmark",
    )

    arguments = parser.parse_args()

    if not arguments.database_url:
        raise ValueError(
            "MEYAAR_DATABASE_URL is not configured."
        )

    metrics = run_evaluation(
        ground_truth_path=(
            arguments.ground_truth
        ),
        database_url=(
            arguments.database_url
        ),
        run_id=arguments.run_id,
        output_directory=(
            arguments.output_directory
        ),
    )

    print(metrics.to_string(index=False))


if __name__ == "__main__":
    main()