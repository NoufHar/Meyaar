# Live testing runbook (real PostGIS)

How to test the Error Analysis Agent against the REAL system:
PostgreSQL+PostGIS -> partner rule engine -> `validation_results` -> agent.

## Prerequisites (once)

```bash
# PostGIS running (colima + container) — from repo root:
colima start --cpu 2 --memory 4
docker context use colima
docker run -d --name meyaar-postgis -e POSTGRES_DB=meyaar_db \
  -e POSTGRES_HOST_AUTH_METHOD=trust -p 5432:5432 --restart unless-stopped \
  postgis/postgis:16-3.4

# agent table (once):
docker exec -i meyaar-postgis psql -U postgres -d meyaar_db \
  < agent/schema/agent_error_analysis.sql

# python deps (once): agent/.venv already has them; partner pipeline needs:
uv pip install --python agent/.venv/bin/python -r agent/requirements.txt geopandas geoalchemy2 pyogrio pyarrow

# data (already present): data/riyadh_roads_clean.geojson, data/riyadh_buildings_clean.geojson
```

## Fastest: one command

```bash
bash agent/scripts/live_test.sh
```
Samples both layers, injects deliberate errors, runs the partner engine
(prints fresh run_ids), runs the agent on both runs, verifies persisted rows.

## Manual alternative

```bash
export MEYAAR_DATABASE_URL="postgresql+psycopg2://postgres@localhost:5432/meyaar_db"
export MEYAAR_ALLOW_LLM=false          # deterministic path (no API key needed)

# 1) insert + run rules -> note the run_id (partner code):
PYTHONPATH=. agent/.venv/bin/python - <<'PY'
from src.pipeline import process_dataset
print(process_dataset("data/riyadh_roads_clean.geojson"))
PY

# 2) agent CLI on that run_id:
agent/.venv/bin/python -m agent.cli analyze <run_id>

# 3) API:
agent/.venv/bin/uvicorn agent.api.app:app --reload
curl -X POST localhost:8000/api/validation/<run_id>/analyze
curl localhost:8000/api/validation/<run_id>/analysis
```

## Testing the LLM path (optional)

Set a key in agent/.env (`MEYAAR_LLM_API_KEY`, optional
`MEYAAR_LLM_BASE_URL` + `MEYAAR_LLM_MODEL` for any OpenAI-compatible
provider), then re-run step 2. Agent_model in the saved rows switches from
`template-fallback` to the model name; output schema is identical.

## Unit tests (no DB needed)

```bash
MEYAAR_ALLOW_LLM=false agent/.venv/bin/python -m pytest agent/tests -q   # 48 passed
```

## Cleanup

```bash
colima stop     # stops the VM + container
```

## Known-good run_ids (recreated on each live_test.sh run)

Run `docker exec meyaar-postgis psql -U postgres -d meyaar_db -tAc
"SELECT run_id, count(*) FROM public.agent_error_analysis GROUP BY run_id ORDER BY 2 DESC"`.
