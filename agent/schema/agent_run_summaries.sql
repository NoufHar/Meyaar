-- ============================================================
-- MEYAAR — AGENT RUN SUMMARIES (executive narrative per run)
-- Owned by: Agentic AI role (agent/)
--
-- One row per validation run: a short human-readable executive summary of
-- what the run found and what the agent did about it (analysis + remediation
-- outcome). Written at the end of the LangGraph workflow (summarize node):
-- LLM-generated when a key is configured, deterministic template otherwise —
-- same stored shape either way, so the UI can always show it.
--
-- counts JSONB mirrors the RunSummary rollup + remediation outcome so the
-- dashboard can render chips without another query.
-- ============================================================

CREATE TABLE IF NOT EXISTS public.agent_run_summaries (
    run_id       UUID PRIMARY KEY,
    narrative    TEXT NOT NULL,
    agent_model  TEXT,
    counts       JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_run_summaries_created
    ON public.agent_run_summaries (created_at DESC);
