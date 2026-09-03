from pathlib import Path
from sqlalchemy import text

SUPPORTED_LAYERS = {"roads", "buildings"}

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQL_DIR = PROJECT_ROOT / "sql"


def _read_sql(filename):
    sql_path = SQL_DIR / filename

    if not sql_path.exists():
        raise FileNotFoundError(f"SQL file not found: {sql_path}")

    return sql_path.read_text(encoding="utf-8")


def _table_exists(connection, layer_name):
    return connection.execute(
        text("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = :layer_name
            )
        """),
        {"layer_name": layer_name},
    ).scalar()


def run_rules_for_layer(engine, layer_name, error_limit=500):
    """
    Run all validation rules that apply to one inserted layer.

    roads:
        RD001-RD005 + GIS001-GIS005

    buildings:
        BLD001-BLD004 + GIS001-GIS005
    """

    layer_name = layer_name.lower().strip()

    if layer_name not in SUPPORTED_LAYERS:
        return {
            "status": "failed",
            "message": (
                f"Unsupported layer '{layer_name}'. "
                "Supported layers are: roads, buildings."
            ),
        }

    layer_sql_file = {
        "roads": "roads_rules.sql",
        "buildings": "buildings_rules.sql",
    }[layer_name]

    try:
        common_sql = _read_sql("common_setup.sql")
        layer_sql = _read_sql(layer_sql_file)
        general_sql = _read_sql("general_rules.sql")

        with engine.begin() as connection:
            if not _table_exists(connection, layer_name):
                return {
                    "status": "failed",
                    "message": f"Table public.{layer_name} does not exist.",
                    "layer_name": layer_name,
                }

            # 1) Create result/config tables and a new validation run.
            connection.exec_driver_sql(common_sql)

            # 2) Tell the general rules which layer is being validated.
            connection.execute(
                text(
                    "INSERT INTO _meyaar_context (layer_name) "
                    "VALUES (:layer_name)"
                ),
                {"layer_name": layer_name},
            )

            # 3) Run layer-specific rules.
            connection.exec_driver_sql(layer_sql)

            # 4) Run general GIS rules for this layer only.
            connection.exec_driver_sql(general_sql.replace("%", "%%"))

            run_id = connection.execute(
                text("SELECT run_id FROM _meyaar_run LIMIT 1")
            ).scalar()

            summary_rows = connection.execute(
                text("""
                    SELECT
                        rule_id,
                        layer_name,
                        error_type,
                        severity,
                        COUNT(*) AS errors_found
                    FROM public.validation_results
                    WHERE run_id = :run_id
                    GROUP BY
                        rule_id,
                        layer_name,
                        error_type,
                        severity
                    ORDER BY rule_id, layer_name
                """),
                {"run_id": run_id},
            ).mappings().all()

            total_errors = connection.execute(
                text("""
                    SELECT COUNT(*)
                    FROM public.validation_results
                    WHERE run_id = :run_id
                """),
                {"run_id": run_id},
            ).scalar()

            error_rows = connection.execute(
                text("""
                    SELECT
                        result_id,
                        run_id,
                        layer_name,
                        feature_id,
                        rule_id,
                        error_type,
                        severity,
                        details,
                        detected_at
                    FROM public.validation_results
                    WHERE run_id = :run_id
                    ORDER BY rule_id, feature_id
                    LIMIT :error_limit
                """),
                {
                    "run_id": run_id,
                    "error_limit": error_limit,
                },
            ).mappings().all()

        return {
            "status": "success",
            "layer_name": layer_name,
            "run_id": str(run_id),
            "total_errors": int(total_errors),
            "summary": [dict(row) for row in summary_rows],
            "errors": [
                {
                    **dict(row),
                    "run_id": str(row["run_id"]),
                    "detected_at": (
                        row["detected_at"].isoformat()
                        if row["detected_at"] is not None
                        else None
                    ),
                }
                for row in error_rows
            ],
        }

    except Exception as e:
        return {
            "status": "failed",
            "layer_name": layer_name,
            "message": str(e),
        }
