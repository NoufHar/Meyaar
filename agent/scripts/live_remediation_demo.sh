#!/usr/bin/env bash
# ============================================================
# Live remediation demo — end-to-end on the team PostGIS.
#
#   bash agent/scripts/live_remediation_demo.sh
#
# What it does:
#   1. reseeds public.buildings (500 sampled features, random_state=42)
#   2. injects the standard engine-error fixtures (bowtie, overlap, dup, NULL)
#   3. adds BLD_INJ_SPK — an invalid "spike" polygon that ST_MakeValid CAN
#      repair inside the Polygon column (the auto-fix success case)
#   4. runs the partner rule engine for buildings (fresh run_id)
#   5. runs the agent (template path, no LLM needed) -> analysis + remediation
#   6. prints the remediation audit for the run
#
# Expected result:
#   BLD003/BLD_INJ_SPK  -> auto_fix   applied   (geometry now valid)
#   BLD003/BLD_INJ_BOW  -> auto_fix   failed    (bowtie -> MultiPolygon cannot
#                                                fit Polygon column; rolled back)
#   BLD001/BLD002/BLD004-> human_review pending_review
# ============================================================
set -euo pipefail
cd "$(dirname "$0")/../.."          # repo root (tuwiq-capstone/Meyaar)

DB_URL="${MEYAAR_DATABASE_URL:-postgresql+psycopg2://postgres@localhost:5432/meyaar_db}"
PY=agent/.venv/bin/python

echo "[1/6] reseed buildings (500 sample rows)..."
PYTHONPATH=. "$PY" agent/scripts/_live_reseed.py buildings data/riyadh_buildings_clean.geojson 500 >/dev/null

echo "[2/6] inject standard error fixtures..."
docker exec -i meyaar-postgis psql -U postgres -d meyaar_db -v ON_ERROR_STOP=1 \
    < agent/scripts/_live_inject_buildings.sql >/dev/null

echo "[3/6] add spike feature (auto-fixable invalid geometry)..."
docker exec -i meyaar-postgis psql -U postgres -d meyaar_db -v ON_ERROR_STOP=1 \
    < agent/scripts/_live_inject_spike.sql >/dev/null

echo "[4/6] run rule engine (buildings)..."
RUN_ID="$(PYTHONPATH=. "$PY" agent/scripts/_live_run_layer.py buildings | sed -n 's/^run_id: //p')"
echo "      run_id: $RUN_ID"

echo "[5/6] run agent analysis + remediation (template path)..."
MEYAAR_ALLOW_LLM=false MEYAAR_DATABASE_URL="$DB_URL" "$PY" -m agent.cli analyze "$RUN_ID" >/dev/null 2>&1 || true

echo "[6/6] remediation audit for run $RUN_ID"
docker exec meyaar-postgis psql -U postgres -d meyaar_db -P pager=off -c "
SELECT result_id, rule_id, feature_id,
       action, remediation_type, status,
       human_review_required,
       left(reason, 70) AS reason
FROM public.agent_remediation_actions
WHERE run_id = '$RUN_ID'
ORDER BY result_id;"

echo
echo "Geometry state after the run (auto-fix target should be valid):"
docker exec meyaar-postgis psql -U postgres -d meyaar_db -P pager=off -c "
SELECT feature_id, ST_IsValid(geometry) AS valid_now, GeometryType(geometry) AS gt
FROM public.buildings
WHERE feature_id IN ('BLD_INJ_SPK','BLD_INJ_BOW')
ORDER BY feature_id;"

echo
echo "Run id for the UI/API: $RUN_ID"
