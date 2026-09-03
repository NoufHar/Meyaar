-- ============================================================
-- MEYAAR - COMMON VALIDATION SETUP
-- Called by validation_tools.py before layer rules.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.validation_results (
    result_id      BIGSERIAL PRIMARY KEY,
    run_id         UUID NOT NULL,
    layer_name     TEXT NOT NULL,
    feature_id     TEXT,
    rule_id        TEXT NOT NULL,
    error_type     TEXT NOT NULL,
    severity       TEXT NOT NULL,
    details        TEXT,
    detected_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_validation_results_run
    ON public.validation_results(run_id);

CREATE INDEX IF NOT EXISTS idx_validation_results_rule
    ON public.validation_results(rule_id, layer_name);

CREATE TABLE IF NOT EXISTS public.meyaar_required_attributes (
    layer_name   TEXT NOT NULL,
    column_name  TEXT NOT NULL,
    PRIMARY KEY (layer_name, column_name)
);

CREATE TABLE IF NOT EXISTS public.meyaar_expected_types (
    layer_name    TEXT NOT NULL,
    column_name   TEXT NOT NULL,
    expected_type TEXT NOT NULL,
    PRIMARY KEY (layer_name, column_name)
);

CREATE TABLE IF NOT EXISTS public.meyaar_allowed_values (
    layer_name    TEXT NOT NULL,
    column_name   TEXT NOT NULL,
    allowed_value TEXT NOT NULL,
    PRIMARY KEY (layer_name, column_name, allowed_value)
);

DROP TABLE IF EXISTS _meyaar_run;
CREATE TEMP TABLE _meyaar_run AS
SELECT gen_random_uuid() AS run_id;

DROP TABLE IF EXISTS _meyaar_context;
CREATE TEMP TABLE _meyaar_context (
    layer_name TEXT NOT NULL
);
