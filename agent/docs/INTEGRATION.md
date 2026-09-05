# Meyaar — Agent Integration Guide (for Backend & UI colleagues)

One page to wire the **Error Analysis Agent** into your work.
Everything below is real and tested against the live system (PostGIS 16, run
`316525f7-a7e3-43bd-81a5-7f442397dd1f`).

Owner of this layer: Person 1 (AI Agent & Error Analysis). Code: `agent/`.

---

## 1. What this layer does (and does NOT)

- **It reads** `public.validation_results` (produced by the PostGIS rule
  engine: BLD001-004, RD001-005, GIS001-005).
- **It writes** `public.agent_error_analysis` (its own table — never touches
  your GIS tables; all reads are read-only).
- **It returns** structured JSON per error + a run-level summary, and answers
  chat questions grounded ONLY in that data.
- **It never** detects geometry errors itself — the SQL engine is the source
  of truth.

Data contract in → out:

```
public.validation_results            public.agent_error_analysis
 result_id      BIGINT      ─────►    result_id      (link)
 run_id         UUID                 run_id, layer_name, feature_id,
 layer_name                           rule_id, error_type, severity,
 feature_id                           status, explanation, cause,
 rule_id                              recommendation, human_review_required,
 error_type                           related_features jsonb,
 severity                             insufficient_context, agent_model,
 details                              analyzed_at
```

---

## 2. Run lifecycle (one UUID rules them all)

```
engine run  ──creates──►  run_id (UUID)   ──►  validation_results rows
        run_id is the ONLY key you need.
agent analyze(run_id)  ──writes──►  agent_error_analysis (idempotent upsert)
GET analysis(run_id)   ──returns──►  summary + every analysis
POST chat(run_id)      ──answers──►  grounded text + source ids
```

- Re-analyzing the same run is safe (upsert on `run_id + result_id`).
- A new engine run = a NEW UUID (list existing ones with the SQL below).

```sql
-- find runs + how many errors each has
SELECT run_id, layer_name, count(*) AS errors
FROM public.validation_results
GROUP BY run_id, layer_name
ORDER BY max(detected_at) DESC;
```

---

## 3. API (standalone or mounted)

### Standalone (for dev/UI work now)

```bash
cd ~/Desktop/tuwiq-capstone/Meyaar
agent/.venv/bin/uvicorn agent.api.app:app --reload
# Chat UI: http://127.0.0.1:8000/   ·  OpenAPI docs: http://127.0.0.1:8000/docs
```

### Mount into your backend (Person 2)

```python
# backend/main.py (or wherever your FastAPI app lives)
from agent.api.router import router as analysis_router

app.include_router(analysis_router, prefix="/api")
```

Dependency note: the router's default repository connects with
`MEYAAR_DATABASE_URL` (default `postgresql+psycopg2://postgres@localhost:5432/meyaar_db`).
Override it by replacing the `get_repository` dependency if your backend owns
the DB session:

```python
from agent.api import router as ar
from agent.db.postgres import PostgresRepository

app.dependency_overrides[ar.get_repository] = lambda: PostgresRepository("your://url")
```

### Machine-readable contract (THE single file)

`agent/api/openapi.json` — full OpenAPI 3 spec of every endpoint. Import it
into Postman/Insomnia/Stoplight, or generate typed clients/types:

```bash
npx openapi-typescript agent/api/openapi.json > api-types.ts   # frontend types
```

Regenerate whenever routes change:
`python -c "from agent.api.app import app; import json; json.dump(app.openapi(), open('agent/api/openapi.json','w'), indent=2)"`

---

## 4. Endpoints

### POST `/api/validation/{run_id}/analyze`
Triggers analysis for a run (LLM or deterministic template — same schema).
```bash
curl -X POST http://127.0.0.1:8000/api/validation/316525f7-a7e3-43bd-81a5-7f442397dd1f/analyze
```
```json
{ "run_id": "316525f7-a7e3-43bd-81a5-7f442397dd1f",
  "status": "completed",
  "total_errors_analyzed": 9,
  "message": "Analyzed 9 validation error(s)" }
```
> Slow? It runs synchronously today (fine for runs ≤ a few hundred errors —
> the engine caps results at 500 per run). If the UI needs async, ask Person 1
> to add a job/task wrapper.

### GET `/api/validation/{run_id}/analysis`
Everything the map + report + UI need.
```bash
curl http://127.0.0.1:8000/api/validation/316525f7-a7e3-43bd-81a5-7f442397dd1f/analysis
```
Shape (full live sample in `agent/docs/_sample_response.json`):
```json
{
  "run_id": "316525f7-a7e3-43bd-81a5-7f442397dd1f",
  "summary": {
    "total_errors": 9, "critical_errors": 1, "high_errors": 6,
    "medium_errors": 2, "most_common_error": "Road Undershoot",
    "priority_actions": [
      "Resolve critical errors first (missing geometry / CRS / coordinates)",
      "Review heuristic topology candidates flagged for human review"
    ],
    "counts_by_rule": { "RD001": 2, "RD002": 4, "RD003": 2, "RD005": 1 },
    "counts_by_layer": { "roads": 9 }
  },
  "analyses": [{
    "result_id": 95,
    "run_id": "316525f7-…",
    "layer_name": "roads",
    "feature_id": "RD_INJ_NULL",
    "rule_id": "RD005",
    "error_type": "Missing Geometry",
    "severity": "critical",
    "status": "confirmed",
    "explanation": "Missing Geometry detected on roads feature RD_INJ_NULL by PostGIS rule RD005 (severity: critical). Rule engine details: Road geometry is NULL or empty.",
    "cause": "Rule RD005 (Missing Geometry): Road row has NULL or empty geometry.",
    "recommendation": "Provide the missing road geometry from the authoritative source, or remove the row if it is not a road.",
    "human_review_required": false,
    "related_features": [],
    "insufficient_context": false,
    "agent_model": "minimax/minimax-m3:free"
  }]
}
```

### POST `/api/validation/{run_id}/chat`
Grounded Q&A about a run. Requires the LLM key configured server-side
(`MEYAAR_LLM_API_KEY` in `agent/.env`) — otherwise HTTP 503.
```bash
curl -X POST http://127.0.0.1:8000/api/validation/316525f7-a7e3-43bd-81a5-7f442397dd1f/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "What should I fix first?"}'
```
```json
{
  "question": "What should I fix first?",
  "answer": "Fix the critical error first: rule RD005 on RD_INJ_NULL (missing geometry)…",
  "sources": ["RD005@RD_INJ_NULL"]
}
```
`sources` are already filtered to ids that exist in the run — safe to render
as chips and link to the map.

---

## 5. Status field — UI MUST respect this (most important rule)

`status` per analysis is one of:

| status | meaning | UI treatment |
|---|---|---|
| `confirmed` | deterministic rule, real error | show as error, red |
| `candidate` | heuristic (RD001/RD002 only) — NOT confirmed | amber, mark "needs review", never auto-fix |
| `informational` | unknown/unrecognized rule | grey, not an error |
| `insufficient_context` | no details + no feature record | grey "cannot explain" |

`human_review_required: true` ⇔ status `candidate`. Never present a candidate
as a confirmed error.

---

## 6. Frontend / map integration

Every analysis row carries the fields the map needs to click → zoom → explain:

```
feature_id    -> select/zoom the feature (layer_name tells which PostGIS table)
layer_name    -> "roads" | "buildings"
rule_id       -> stable id (BLD001…, RD001…, GIS001…)
error_type    -> human label
severity      -> critical | high | medium  (from the engine, never altered)
status        -> confirmed | candidate | informational | insufficient_context
explanation   -> plain-language why (safe to display as-is)
recommendation-> suggested fix
related_features -> other feature ids involved (e.g. the building it overlaps)
```

Suggested interactions:
- Error list = `analyses[]`; filter chips by layer/rule/severity/status.
- Clicking an error → zoom to `feature_id` in `layer_name` → show
  explanation + recommendation + severity + status.
- "Run summary" panel = `summary` (totals, most common error, priority actions).
- Candidate rows get a "review" workflow (mark false-positive/confirm) — that
  write-back does not exist yet; coordinate if the UI needs it.

Live sample to model against: `agent/docs/_sample_response.json`
(re-run to refresh: it's fetched from the real DB).
Chat UI reference implementation: `agent/api/static/index.html` (no build step).

---

## 7. Error codes you will see

| HTTP | meaning |
|---|---|
| 200 | ok |
| 404 | no analysis for that run yet → call `/analyze` first (chat) / no rows |
| 422 | `run_id` is not a UUID / bad body |
| 503 | chat called but no LLM key configured |
| 502 | LLM/tool failure on this attempt (retry) |

---

## 8. Config the backend must know

| env | default | purpose |
|---|---|---|
| `MEYAAR_DATABASE_URL` | postgresql+psycopg2://postgres@localhost:5432/meyaar_db | DB for reads + agent table writes |
| `MEYAAR_LLM_API_KEY` | (empty) | enables LLM explanations/chat (any OpenAI-compatible: OpenAI/DeepSeek/OpenRouter) |
| `MEYAAR_LLM_BASE_URL` / `MEYAAR_LLM_MODEL` | https://openrouter.ai/api/v1 / minimax/minimax-m3:free | LLM endpoint + model |
| `MEYAAR_ALLOW_LLM` | true | set false to force deterministic template (same JSON) |
| `MEYAAR_TTS_ENGINE` | macos | CLI chat `--speak` TTS (macos/none) |

DB access for the agent table:
```sql
CREATE TABLE public.agent_error_analysis …   -- see agent/schema/agent_error_analysis.sql
```

---

## 9. Running the whole thing locally (for your own testing)

```bash
bash agent/scripts/live_test.sh    # samples data -> engine runs -> agent analyze -> prints new run ids
# then use one printed run_id with the endpoints above
```

Need more context from the DB (feature geometry type/SRID/centroid)? It is
already inside explanations, and the raw query tool is read-only by design.
