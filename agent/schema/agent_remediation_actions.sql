-- ============================================================
-- MEYAAR — AGENT REMEDIATION ACTIONS  (audit / provenance)
-- Owned by: Agentic AI role (agent/)
--
-- One row per (run_id, result_id) recording what the agent did about a
-- validated error, so the dashboard / reviewers can distinguish:
--
--   action = auto_fix      + status = applied        -> automatically fixed
--   action = auto_fix      + status = failed         -> execution failed (logged, rolled back)
--   action = human_review  + status = pending_review -> queued for a human reviewer
--   action = no_action     + status = none           -> nothing safe to do
--
-- The LLM proposes explanations/recommendations only; the remediation
-- decision (action / remediation_type / human_review_required) is produced
-- by deterministic policy code reading rules/registry.json, and the actual
-- database mutation happens through one whitelisted repository method
-- (apply_geometry_repair). before_state/after_state store small JSONB
-- snapshots (e.g. geometry_type/srid/geojson) for auditability.
-- ============================================================

CREATE TABLE IF NOT EXISTS public.agent_remediation_actions (
    remediation_id       BIGSERIAL PRIMARY KEY,
    run_id               UUID NOT NULL,
    result_id            BIGINT NOT NULL,

    -- Denormalized source row (same keys as agent_error_analysis)
    layer_name           TEXT NOT NULL,
    feature_id           TEXT,
    rule_id              TEXT NOT NULL,

    -- Decision (deterministic policy output)
    action               TEXT NOT NULL,   -- auto_fix | human_review | no_action
    remediation_type     TEXT,            -- geometry_repair | attribute_correction | crs_transform | human_review
    status               TEXT NOT NULL,   -- applied | failed | pending_review | none

    -- Why
    issue                TEXT NOT NULL,   -- what the engine flagged (error_type + detail)
    reason               TEXT NOT NULL,   -- why auto-fix was (not) performed
    recommended_action   TEXT,            -- registry/analysis guidance for the human

    -- Provenance / audit
    before_state         JSONB NOT NULL DEFAULT '{}'::jsonb,
    after_state          JSONB NOT NULL DEFAULT '{}'::jsonb,
    agent_model          TEXT,
    human_review_required BOOLEAN NOT NULL DEFAULT FALSE,
    executed_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT agent_remediation_unique_run_result UNIQUE (run_id, result_id)
);

CREATE INDEX IF NOT EXISTS idx_agent_remediation_run
    ON public.agent_remediation_actions (run_id);

CREATE INDEX IF NOT EXISTS idx_agent_remediation_status
    ON public.agent_remediation_actions (status, action);
