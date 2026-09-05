# Meyaar — Agentic Error Analysis Layer

**Owner:** Agentic AI Engineer role. Everything here lives under `agent/`.

This package implements the **Error Analysis Agent** that sits on top of the
PostGIS Rule Engine (`sql/gis_rule_engine.sql`). The rule engine detects;
this agent interprets.

> PostGIS / Rule Engine = **Detection**
> AI Agent = **Interpretation, reasoning, prioritization, explanation,
> contextual analysis, and recommendations**

The agent NEVER replaces PostGIS logic, never runs destructive SQL, and never
modifies production GIS tables. Its only write target is its own
`public.agent_error_analysis` table (schema in `agent/schema/`).

---

## Workflow (LangGraph)

```
validation_results
      │  fetch_results(run_id)
      ▼
 load ──(results?)──► prepare/groups ──► analyze ──► validate ──► save ──► summarize ──► END
      │                    │                │            │           │
      │                    │  bulk feature  │ LLM per     repair     upsert to
      │                    │  context via   │ (layer,     status/     agent_error_
      │                    │  repository    │ rule) or    schema      analysis
      │                    │                │ template
      └──── no results ───► summarize (zero summary) ─────────────────────► END
```

- **load** — `Repository.fetch_results(run_id)` from `public.validation_results`
- **prepare** — groups errors by `(layer_name, rule_id)`; fetches lightweight
  context for every referenced feature in one batched query (never full
  geometries) via `get_related_features`
- **analyze** — one call per group (LLM when configured, deterministic
  template otherwise — same JSON schema, both paths)
- **validate** — enforces invariants: heuristic rules (RD001/RD002) can never
  be anything but `candidate` + `human_review_required=true`; severities are
  copied from the engine untouched; malformed LLM rows are repaired
- **save** — idempotent upsert (`ON CONFLICT (run_id, result_id)`)
- **summarize** — run-level rollup: totals by severity/layer/rule, most common
  error, priority actions (critical first, heuristic review last)

## Classification rules

| Rule | Engine severity | Type | Agent status | Human review |
|---|---|---|---|---|
| BLD001 Building Overlap | high | deterministic | confirmed | no |
| BLD002 Duplicate Buildings | medium | deterministic | confirmed | no |
| BLD003 Invalid Geometry | high | deterministic | confirmed | no |
| BLD004 Missing Geometry | critical | deterministic | confirmed | no |
| RD001 Road Overshoot | high | **heuristic** | **candidate** | **yes** |
| RD002 Road Undershoot | high | **heuristic** | **candidate** | **yes** |
| RD003 Duplicate Roads | medium | deterministic | confirmed | no |
| RD004 Invalid Geometry | high | deterministic | confirmed | no |
| RD005 Missing Geometry | critical | deterministic | confirmed | no |
| GIS001 Missing/Wrong CRS | critical | deterministic | confirmed | no |
| GIS002 Invalid Coordinates | critical | deterministic | confirmed | no |
| GIS003 Missing Required Attributes | high | deterministic | confirmed | no |
| GIS004 Wrong Data Type | medium | deterministic | confirmed | no |
| GIS005 Invalid Attribute Values | medium | deterministic | confirmed | no |

Severities are **never upgraded/downgraded** by the agent. When a result has
no details and no feature context, the analysis returns
`status: insufficient_context` (heuristics stay `candidate` but are flagged)
instead of hallucinating.

Rule semantics live in `agent/rules/registry.json` (maintainable config), not
inside the LLM prompt.

## Agent tools

All tools are plain typed callables against the injected `Repository`
(`agent/tools/`), so they are testable without a database:

1. `get_validation_results(run_id, rule_id?, layer_name?, feature_id?, severity?)`
2. `get_feature_context(layer_name, feature_id)` — geometry type, SRID,
   centroid, bbox (no full geometry to the LLM)
3. `get_related_features(layer_name, feature_ids)` — bulk context
4. `query_postgis(sql, params?)` — read-only; guarded by
   `agent/tools/sql_guard.py` AND by `default_transaction_read_only=on` on the
   engine (defense in depth)
5. `get_rule_definition(rule_id)` — from `rules/registry.json`

## Package layout

```
agent/
├── core/        config (env), LLM factory, pydantic models
├── rules/       registry.json + loader (rule-definition system)
├── db/          Repository interface + Postgres + InMemory implementations
├── tools/       the five agent tools + read-only SQL guard
├── graph/       LangGraph: state, nodes, builder
├── api/         FastAPI router + standalone app + openapi.json contract
├── chat.py      grounded chat service (text + sources)
├── voice.py     thin TTS/STT integration (macOS say + browser APIs)
├── schema/      agent_error_analysis.sql (DDL)
├── cli.py       terminal runner
└── tests/       fixtures + rule/tool/graph/API/chat/voice tests
```

Docs: `docs/INTEGRATION.md` (for backend/UI colleagues, incl. OpenAPI file),
`docs/testing.md`, `docs/live-testing.md`, API spec `api/openapi.json`,
live response sample `docs/_sample_response.json`.

## Database setup

```bash
# 1. create the analysis table (run against meyaar_db with postgis)
psql -d meyaar_db -f agent/schema/agent_error_analysis.sql

# 2. connection settings (defaults match src/insertion/database.py)
cp agent/.env.example agent/.env   # edit MEYAAR_DATABASE_URL if needed
```

## Run

```bash
cd ~/Desktop/tuwiq-capstone/Meyaar

# offline demo (no Postgres needed) against the sample fixture:
agent/.venv/bin/python -m agent.cli analyze 8f0a1b2c-3d4e-4f5a-8b9c-0d1e2f3a4b5c \
    --demo agent/tests/fixtures/sample_run.json

# against the team PostGIS (needs a real run_id in validation_results):
agent/.venv/bin/python -m agent.cli analyze <run_uuid>

# API (standalone during development):
agent/.venv/bin/uvicorn agent.api.app:app --reload
#   POST /api/validation/{run_id}/analyze
#   GET  /api/validation/{run_id}/analysis
#   POST /api/validation/{run_id}/chat        {"question": "why is BLD_102 flagged?"}

# Chat about a run's engine results (needs MEYAAR_LLM_API_KEY):
agent/.venv/bin/python -m agent.cli chat <run_id>                    # interactive REPL
agent/.venv/bin/python -m agent.cli chat <run_id> --ask "What should I fix first?"
agent/.venv/bin/python -m agent.cli chat <run_id> --ask "..." --speak   # read answer aloud (macOS say)

# Voice in the chat UI (http://127.0.0.1:8000/): 🎤 = ask by voice (browser
# Web Speech API), 🔊 = read the answer aloud. Engines/config in agent/voice.py.
agent/.venv/bin/python -c "from agent.voice import available_engines; print(available_engines())"

# Backend teammate integration: mount the router
#   from agent.api.router import router
#   app.include_router(router, prefix="/api")
```

## LLM (optional)

Set `MEYAAR_LLM_API_KEY` (+ optional `MEYAAR_LLM_BASE_URL`, `MEYAAR_LLM_MODEL`
for any OpenAI-compatible provider) in `agent/.env`. Without a key the agent
runs fully deterministically — same JSON schema, zero API calls, CI-safe.

## Test

```bash
agent/.venv/bin/python -m pytest agent/tests -q
# 48 tests: registry semantics for all 13 rules, tool + SQL-guard behaviour,
# full-run analysis, heuristic classification, missing context,
# DB failures, malformed/lying LLM output, API endpoints.
```

## Reliability guarantees

- never fabricates feature ids, locations, overlap areas, or distances —
  explanation text only echoes `details` + retrieved context
- heuristic candidates are never reported as confirmed
- `insufficient_context` instead of guessing
- destructive SQL rejected by guard + read-only DB session
- DB/tool failures are logged per step and never crash the whole run
- LLM retries with template fallback; invented `result_id`s are dropped

## Open items needing GIS/human validation

- RD001/RD002 5 m tolerance semantics and false-positive rates
- exact rule descriptions/recommendations in `registry.json` should be
  reviewed against the final GeoSA selections by the rule-engine owner
- `agent_error_analysis` table needs to be created on the shared DB
- live PostGIS integration test once `meyaar_db` is reachable
