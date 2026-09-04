-- ============================================================
-- MEYAAR — AGENT ERROR ANALYSIS
-- Owned by: Agentic AI role (agent/)
--
-- Stores the Error Analysis Agent's structured interpretation of
-- rows produced by the PostGIS rule engine (public.validation_results).
-- The original validation_results table is NOT modified.
--
-- Improvements over the suggested schema:
--   * denormalized layer/feature/rule/severity so the map dashboard can
--     zoom to an error without a join
--   * related_features JSONB for click-through context
--   * UNIQUE(run_id, result_id) makes re-analysis idempotent (upsert)
-- ============================================================

CREATE TABLE IF NOT EXISTS public.agent_error_analysis (
    analysis_id          BIGSERIAL PRIMARY KEY,
    run_id               UUID NOT NULL,
    result_id            BIGINT NOT NULL,

    -- Denormalized source row (map integration + traceability)
    layer_name           TEXT NOT NULL,
    feature_id           TEXT,
    rule_id              TEXT NOT NULL,
    error_type           TEXT NOT NULL,
    severity             TEXT NOT NULL,

    -- Agent interpretation
    status               TEXT NOT NULL,          -- confirmed | candidate | informational | insufficient_context
    explanation          TEXT NOT NULL,
    cause                TEXT,
    recommendation       TEXT,
    human_review_required BOOLEAN NOT NULL DEFAULT FALSE,
    related_features     JSONB NOT NULL DEFAULT '[]'::jsonb,
    insufficient_context BOOLEAN NOT NULL DEFAULT FALSE,

    -- Provenance
    agent_model          TEXT,
    analyzed_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT agent_error_analysis_unique_run_result UNIQUE (run_id, result_id)
);

CREATE INDEX IF NOT EXISTS idx_agent_analysis_run
    ON public.agent_error_analysis (run_id);

CREATE INDEX IF NOT EXISTS idx_agent_analysis_rule
    ON public.agent_error_analysis (rule_id, layer_name);
