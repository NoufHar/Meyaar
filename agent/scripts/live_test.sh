#!/usr/bin/env bash
# ============================================================
# Meyaar LIVE end-to-end test: real PostGIS -> partner rule
# engine -> Error Analysis Agent (roads + buildings).
#
# Requires: running PostGIS on localhost:5432 with db meyaar_db
# (e.g. the meyaar-postgis container) + data/riyadh_*_clean.geojson.
#
# Usage:  bash agent/scripts/live_test.sh
# ============================================================
set -euo pipefail
cd "$(dirname "$0")/../.."          # repo root
PY=agent/.venv/bin/python
DBURL="postgresql+psycopg2://postgres@localhost:5432/meyaar_db"
export MEYAAR_DATABASE_URL="$DBURL"
export MEYAAR_ALLOW_LLM="false"

echo "== 1/6 check PostGIS =="
docker exec meyaar-postgis pg_isready -U postgres -h localhost -d meyaar_db >/dev/null
echo "   PostGIS up (meyaar-postgis)"

echo "== 2/6 reseed sampled layers through partner insertion helpers =="
PYTHONPATH=. $PY agent/scripts/_live_reseed.py roads     data/riyadh_roads_clean.geojson     2000 | tail -1
PYTHONPATH=. $PY agent/scripts/_live_reseed.py buildings data/riyadh_buildings_clean.geojson  500  | tail -1

echo "== 3/6 inject deliberate errors (dup/invalid/null/overlap/topology) =="
docker exec -i meyaar-postgis psql -U postgres -d meyaar_db -q -v ON_ERROR_STOP=1 < agent/scripts/_live_inject_roads.sql
docker exec -i meyaar-postgis psql -U postgres -d meyaar_db -q -v ON_ERROR_STOP=1 < agent/scripts/_live_inject_buildings.sql
echo "   injected"

echo "== 4/6 run partner rule engine (creates validation_results + run_id) =="
ROADS_OUT=$(PYTHONPATH=. $PY agent/scripts/_live_run_layer.py roads | grep '^run_id:' | awk '{print $2}')
BLDG_OUT=$(PYTHONPATH=. $PY agent/scripts/_live_run_layer.py buildings | grep '^run_id:' | awk '{print $2}')
echo "   roads run_id:     $ROADS_OUT"
echo "   buildings run_id: $BLDG_OUT"
test -n "$ROADS_OUT" && test -n "$BLDG_OUT"

echo "== 5/6 Error Analysis Agent on both runs =="
$PY -m agent.cli analyze "$ROADS_OUT" | head -12
echo "   ---"
$PY -m agent.cli analyze "$BLDG_OUT" | head -12

echo "== 6/6 verify persisted analyses + run summary =="
docker exec meyaar-postgis psql -U postgres -d meyaar_db -tAc \
  "SELECT run_id, count(*) FROM public.agent_error_analysis WHERE run_id IN ('$ROADS_OUT','$BLDG_OUT') GROUP BY run_id"

echo
echo "DONE. Re-run the agent any time with:"
echo "  MEYAAR_DATABASE_URL='$DBURL' agent/.venv/bin/python -m agent.cli analyze <run_id>"
echo "API (optional):"
echo "  agent/.venv/bin/uvicorn agent.api.app:app --reload"
