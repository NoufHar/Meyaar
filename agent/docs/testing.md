# How to test the Error Analysis Agent

Four layers of testing, from zero-dependency to full live system.

## 1) Unit tests — no DB, no LLM (fastest, always works)

```bash
cd ~/Desktop/tuwiq-capstone/Meyaar
MEYAAR_ALLOW_LLM=false agent/.venv/bin/python -m pytest agent/tests -q
# expect: 96 passed
```

Runs against an in-memory repository + stub LLMs. Covers:

| File | What it proves |
|---|---|
| test_rules.py | registry semantics for ALL 13 engine rules (severity, deterministic vs heuristic, human-review) |
| test_tools.py | SQL guard accepts SELECT-only, rejects INSERT/UPDATE/DELETE/DROP/… ; tools return None/{}/[] instead of inventing |
| test_analysis.py | full-run analysis; RD001/RD002 stay candidate; missing context -> insufficient_context; DB failure logged not fatal; malformed LLM JSON -> template fallback; LLM inventing result_id -> dropped; LLM cannot downgrade a heuristic to confirmed; summary counts; persisted executive narrative (template + LLM + clean-run) |
| test_measurements.py | get_spatial_measurements shape (length_m/area_m2/vertex_count/centroid/bbox, relationship block), N/A = None, missing feature = None; registry remediation policy fields for all rules (auto-fix only BLD003/RD004) |
| test_remediation.py | the 9 trainer scenarios: auto-fix applied, RD001/RD002 human review, missing geometry never invented, LLM invalid action rejected, LLM heuristic auto-fix claim overridden, SQL failure recorded + others continue, LLM-disabled determinism, clean run |
| test_chat.py | grounded answers, source filtering (fake ids dropped), requires LLM; chat context includes the remediation audit (counts + items) and still works when the audit table is missing |
| test_api.py | POST analyze, GET analysis (404 before analyze), GET remediation, malformed UUID 422, narrative in analysis summary |

Run one file: `... -m pytest agent/tests/test_analysis.py -q`
Run one case: `... -m pytest agent/tests/test_analysis.py::test_heuristic_rows_are_candidates_and_persisted`

## 2) Live end-to-end (real PostGIS + partner engine + agent) — one command

Requires: postgis container running (see agent/docs/live-testing.md prerequisites).

```bash
bash agent/scripts/live_test.sh
```

What it does: samples roads (2000) + buildings (500) from data/riyadh_*.geojson
through the partner's own insertion helpers -> injects deliberate errors ->
runs the partner rule engine (prints fresh run_ids) -> runs the agent on both
runs -> verifies rows persisted in agent_error_analysis.

Expected: 9 roads errors + 5 buildings errors, RD001/RD002 shown REVIEW/candidate,
deterministic rules confirmed, and a final `run_id|count` table (9 and 5).

Remediation demo (shows auto-fix + review queue + audit on buildings):
```bash
bash agent/scripts/live_remediation_demo.sh
# prints a remediation audit: BLD003 spike -> auto_fix/applied (geometry now
# valid), BLD003 bowtie -> auto_fix/failed (rolled back, human re-digitization),
# BLD001/BLD002/BLD004 -> human_review/pending_review
```

## 3) Manual live flow (test with any dataset / any run the engine produces)

```bash
export MEYAAR_DATABASE_URL="postgresql+psycopg2://postgres@localhost:5432/meyaar_db"

# A) produce a run from a file (partner pipeline) and read the run_id:
PYTHONPATH=. agent/.venv/bin/python -c \
  "from src.pipeline import process_dataset; print(process_dataset('data/riyadh_roads_clean.geojson'))"

# B) analyze that run (or any run_id already in public.validation_results):
agent/.venv/bin/python -m agent.cli analyze <run_id>

# C) re-analyze is idempotent (upsert on run_id+result_id) — safe to rerun.
```

Checklist when inspecting CLI output:
- heuristic rules (RD001/RD002) show `[REVIEW]` + status candidate — never confirmed
- deterministic rules show `confirmed` and NO review flag
- severities are copied from the engine untouched (critical/high/medium)
- explanations echo engine details (real areas/ids) — nothing invented
- `insufficient_context` appears ONLY when a result has no details AND no feature context

## 4) LLM path vs deterministic path

With a key in agent/.env (see agent/.env: MEYAAR_LLM_API_KEY, MEYAAR_LLM_BASE_URL, MEYAAR_LLM_MODEL):

```bash
# LLM path (default once key is set):
agent/.venv/bin/python -m agent.cli analyze <run_id>

# Force deterministic for comparison (same JSON shape):
MEYAAR_ALLOW_LLM=false agent/.venv/bin/python -m agent.cli analyze <run_id>
```

Verify the LLM was used: re-fetch shows agent_model = your model (not template-fallback),
and trace contains `[analyze] <rule>: llm`. If the LLM fails/times out the run still
completes via template fallback (by design).

## 5) API endpoints

```bash
agent/.venv/bin/uvicorn agent.api.app:app --reload   # http://127.0.0.1:8000

curl -X POST http://127.0.0.1:8000/api/validation/<run_id>/analyze
# {"run_id": "...", "status": "completed", "total_errors_analyzed": 9}

curl http://127.0.0.1:8000/api/validation/<run_id>/analysis
# {run_id, summary{total, critical, high, medium, most_common_error,
#    priority_actions, counts_by_rule, counts_by_layer, narrative}, analyses[]}
#   narrative = per-run executive summary (agent_run_summaries)

curl http://127.0.0.1:8000/api/validation/<run_id>/remediation
# {run_id, remediation[{action: auto_fix|human_review|no_action,
#    status: applied|failed|pending_review|none, reason, recommended_action,
#    before_state, after_state, ...}]}  -> the review queue / audit
```

OpenAPI docs: http://127.0.0.1:8000/docs

## 6) Inspect the database directly

```bash
docker exec meyaar-postgis psql -U postgres -d meyaar_db -c \
 "SELECT run_id, rule_id, status, severity, human_review_required FROM public.agent_error_analysis ORDER BY analyzed_at DESC LIMIT 15"
docker exec meyaar-postgis psql -U postgres -d meyaar_db -c \
 "SELECT run_id, count(*) FROM public.agent_error_analysis GROUP BY run_id"
docker exec meyaar-postgis psql -U postgres -d meyaar_db -c \
 "SELECT run_id, action, status, count(*) FROM public.agent_remediation_actions GROUP BY run_id, action, status ORDER BY 1 DESC"
docker exec meyaar-postgis psql -U postgres -d meyaar_db -c \
 "SELECT run_id, left(narrative, 80) FROM public.agent_run_summaries ORDER BY created_at DESC LIMIT 5"
```

## Troubleshooting

- `enabled: False` after adding a key -> key empty/quoted in agent/.env (no quotes/spaces)
- LLM 404/model not found -> fix MEYAAR_LLM_MODEL to an exact OpenRouter id
- Container "gone" -> docker context use colima
- Roads LLM explanations lack geometry context -> you are on an old build; the
  feature_id id-column fix is in the current code (resolved via information_schema)
