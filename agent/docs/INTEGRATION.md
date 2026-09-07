# Meyaar — Agent Integration Guide (for Backend & UI colleagues)

One page to wire the **Error Analysis Agent** into your work.
Everything below is real and tested against the live system (PostGIS 16, run
`316525f7-a7e3-43bd-81a5-7f442397dd1f`).

Owner of this layer: Person 1 (AI Agent & Error Analysis). Code: `agent/`.

---

## 1. What this layer does (and does NOT)

- **It reads** `public.validation_results` (produced by the PostGIS rule
  engine: BLD001-004, RD001-005, GIS001-005) — read-only, guarded.
- **It writes three of its OWN tables** (`agent/schema/*.sql`):
  - `agent_error_analysis` — interpretation per error
  - `agent_remediation_actions` — what the agent did about each error
    (auto-fixed / queued for human / no action) + audit
  - `agent_run_summaries` — one executive narrative per run
- **One whitelisted mutation** on source layers: `apply_geometry_repair`
  (transactional `ST_MakeValid`) — ONLY for policy-approved rules
  (BLD003/RD004 invalid geometry). No other write ever touches your tables.
- **It returns** structured JSON per error + a run-level summary + a
  remediation audit, and answers chat questions grounded ONLY in that data.
- **It never** detects geometry errors itself — the SQL engine is the source
  of truth, and the LLM never decides or executes fixes (see §4.2).

Data contract in → out:

```
public.validation_results            agent tables (agent/schema/)
 result_id      BIGINT      ─────►    agent_error_analysis.result_id
 run_id         UUID                  agent_remediation_actions.result_id
 layer_name                           agent_run_summaries.run_id
 feature_id
 rule_id
 error_type
 severity
 details
```

---

## 2. Run lifecycle (one UUID rules them all)

```
engine run  ──creates──►  run_id (UUID)   ──►  validation_results rows
        run_id is the ONLY key you need.
agent analyze(run_id) ──writes──►  agent_error_analysis (idempotent upsert)
                                  + agent_remediation_actions (auto-fix /
                                    human-review decision per error)
                                  + agent_run_summaries (executive narrative)
GET analysis(run_id)     ──returns──►  summary (incl. narrative) + analyses
GET remediation(run_id)  ──returns──►  audit: what was auto-fixed / queued
POST chat(run_id)        ──answers──►  grounded text + source ids
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
MEYAAR_DEV_NO_AUTH=*** agent/.venv/bin/uvicorn agent.api.app:app --reload
# Chat UI: http://127.0.0.1:8000/   ·  OpenAPI docs: http://127.0.0.1:8000/docs
```

> Auth note (main branch): the production app is `src/api/main.py` — it mounts
> this router and protects every endpoint with login + run access. The
> standalone app above is for local dev; set `MEYAAR_DEV_NO_AUTH=1` to bypass
> auth there (never in production). Agent tests stub auth/access, so they run
> anywhere without a backend.

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
Triggers analysis AND remediation for a run (LLM or deterministic template —
same schema). Idempotent: safe to re-run.
```bash
curl -X POST http://127.0.0.1:8000/api/validation/316525f7-a7e3-43bd-81a5-7f442397dd1f/analyze
```
```json
{ "run_id": "316525f7-a7e3-43bd-81a5-7f442397dd1f",
  "status": "completed",
  "total_errors_analyzed": 9,
  "message": "Analyzed 9 validation error(s)" }
```
`status` is `completed`, or `completed_with_warnings` when a remediation was
attempted and recorded as failed (e.g. a repair the column type cannot
store — it is rolled back and logged, never fatal). The audit row explains
why (see GET `/remediation`).
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
    "counts_by_layer": { "roads": 9 },
    "narrative": "The validation run flagged nine errors across the roads layer… (executive summary, persisted in agent_run_summaries)"
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

### GET `/api/validation/{run_id}/remediation`
The **review queue / audit**: what the agent did about each error. Records are
created by `/analyze` (one per `result_id`).
```bash
curl http://127.0.0.1:8000/api/validation/316525f7-a7e3-43bd-81a5-7f442397dd1f/remediation
```
Record shape (one per error, idempotent upsert):
```json
{ "run_id": "…", "result_id": 95, "layer_name": "roads",
  "feature_id": "RD_INJ_NULL", "rule_id": "RD005",
  "action": "human_review", "remediation_type": "human_review",
  "status": "pending_review",
  "issue": "Missing Geometry: Road geometry is NULL or empty.",
  "reason": "…why auto-fix was (not) performed…",
  "recommended_action": "Provide the missing road geometry from the authoritative source…",
  "before_state": {}, "after_state": {},
  "agent_model": "minimax/minimax-m3:free",
  "human_review_required": true,
  "executed_at": "…" }
```
UI MUST distinguish four states (trainer requirement — never silently drop):

| action | status | meaning | UI treatment |
|---|---|---|---|
| `auto_fix` | `applied` | fixed automatically (BLD003/RD004 geometry repair only) | green "auto-fixed"; show before/after |
| `human_review` | `pending_review` | queued for a human reviewer | amber "needs review"; show `recommended_action` |
| `no_action` | `none` | nothing safe to do (layer-level / unknown rule) | grey; show `recommended_action` as guidance |
| `auto_fix` | `failed` | auto repair attempted, rolled back + logged | red "failed"; reason explains why |

`before_state`/`after_state` hold GeoJSON snapshots for applied repairs (empty
dicts otherwise).

Drawing before/after on the map (Leaflet-ready):
- Both states contain a string field `geojson` — a complete GeoJSON geometry
  (`{"type":"Polygon","coordinates":[...]}`) ready to parse:
  `JSON.parse(record.before_state.geojson)` / `...after_state.geojson`.
- Suggested UX: draw `before` as a red/striped outline ("before — invalid"),
  draw `after` as a green fill ("after — repaired"), overlay both on the same
  feature location, or show a before→after toggle. Only records with
  `action=auto_fix` carry real snapshots; `failed` records keep the `before`
  but no `after` (the repair was rolled back).
- Coordinates are EPSG:4326 (lon/lat) — Leaflet `L.geoJSON(...)` accepts them
  directly; react-leaflet works the same with a `<GeoJSON data=... />`.
- The map can also read `analysis[].feature_id` + `layer_name` to zoom to the
  repaired feature (see §6).

> Chat is remediation-aware: it reads the same audit, so it will truthfully
> answer "what was fixed automatically?" (see POST `/chat`).

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
- "Run summary" panel = `summary` (totals, most common error, priority
  actions) + `summary.narrative` as the executive text at the top.
- Remediation panel / review queue = GET `/remediation`: render the four
  states (auto-fixed / pending review / no action / failed) per error — see
  §4. `recommended_action` is the guidance to show a reviewer; a
  `pending_review` row is where your "confirm / mark false-positive" workflow
  plugs in (write-back does not exist yet — coordinate if the UI needs it).
- Auto-fix before/after: parse `before_state.geojson` / `after_state.geojson`
  and overlay both on the map (see "Drawing before/after" in §4).
- Candidate rows (status `candidate`) get a "review" workflow — see §5.

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

DB access for the agent tables (run all three against meyaar_db once):
```sql
CREATE TABLE public.agent_error_analysis …          -- agent/schema/agent_error_analysis.sql
CREATE TABLE public.agent_remediation_actions …     -- agent/schema/agent_remediation_actions.sql
CREATE TABLE public.agent_run_summaries …           -- agent/schema/agent_run_summaries.sql
```

---

## 9. Running the whole thing locally (for your own testing)

```bash
bash agent/scripts/live_test.sh    # samples data -> engine runs -> agent analyze -> prints new run ids
# then use one printed run_id with the endpoints above
```

Need more context from the DB (feature geometry type/SRID/centroid)? It is
already inside explanations, and the raw query tool is read-only by design.
