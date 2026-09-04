# Meyaar Agent — Teammate Quickstart (share this file)

This is the short version for other team members (backend, UI, data) who want
to run the **Error Analysis Agent** on their own machine and try the chat UI.
Full details: `docs/live-testing.md` and `docs/INTEGRATION.md`.

> One honest note up front: your PostGIS container starts EMPTY. Runs created
> on your machine are yours (each run gets a new UUID). To share one team run,
> point everyone at a shared DB (section 5) instead.

---

## 1. Get the code + environment

```bash
git clone https://github.com/NoufHar/Meyaar.git     # or: git pull inside your clone
cd Meyaar

# Python 3.12 venv with uv (macOS/Linux):
uv venv agent/.venv --python 3.12
uv pip install --python agent/.venv/bin/python -r agent/requirements.txt geopandas geoalchemy2 pyogrio pyarrow

# Windows without uv: install Python 3.12, then
#   python -m venv agent/.venv
#   agent/.venv/Scripts/python -m pip install -r agent/requirements.txt geopandas geoalchemy2 pyogrio pyarrow
```

## 2. Start PostGIS (Docker)

macOS with colima:
```bash
colima start --cpu 2 --memory 4
docker context use colima
```
Windows/macOS with Docker Desktop: just start Docker Desktop.

Then (any OS, once Docker is running):
```bash
docker run -d --name meyaar-postgis -e POSTGRES_DB=meyaar_db \
  -e POSTGRES_HOST_AUTH_METHOD=*** -p 5432:5432 --restart unless-stopped \
  postgis/postgis:16-3.4

# create the agent's table (once):
docker exec -i meyaar-postgis psql -U postgres -d meyaar_db \
  < agent/schema/agent_error_analysis.sql
```

## 3. LLM key (needed for chat / LLM explanations)

`agent/.env` is gitignored — it does NOT come with the repo. Create it from
the example and add your key (any OpenAI-compatible provider):
```bash
cp agent/.env.example agent/.env
# edit agent/.env ->  MEYAAR_LLM_API_KEY=sk-or-...   (OpenRouter)
#                     MEYAAR_LLM_MODEL=minimax/minimax-m3:free   (already set)
```
Verify: `agent/.venv/bin/python -c "from agent.core.config import settings; print(settings.llm_enabled)"` → True

## 4. Generate a run + analyze + chat (needs data files, e.g. data/riyadh_roads_clean.geojson)

```bash
bash agent/scripts/live_test.sh
# prints fresh run ids after analyzing roads + buildings
```
Or manual (see docs/live-testing.md). Then:
```bash
export MEYAAR_DATABASE_URL="postgresql+psycopg2://postgres@localhost:5432/meyaar_db"
agent/.venv/bin/python -m agent.cli analyze <run_id>
agent/.venv/bin/python -m agent.cli chat <run_id> --ask "What should I fix first?"
```

## 5. Run the UI + API

```bash
agent/.venv/bin/uvicorn agent.api.app:app --reload     # http://localhost:8000/
```
- http://localhost:8000/  → chat UI (paste a run UUID → Analyze run → Ask; 🎤 voice, 🔊 read-aloud)
- http://localhost:8000/docs → OpenAPI docs
- agent/api/openapi.json → machine-readable API contract

### Voice on Windows / other machines
- 🔊 read-aloud + text chat: works anywhere (browser TTS).
- 🎤 mic: works on **localhost** (or HTTPS). Plain `http://<ip>:8000` from
  another machine blocks mic (browser secure-context rule) — use localhost or
  HTTPS/tunnel for remote mic.
- CLI `--speak` uses macOS `say` → macOS only (chat still works elsewhere).

### Seeing a teammate's runs / shared DB
Your container is local. For one shared set of runs, either:
- everyone runs their own (reproducible), or
- point all machines at one DB:
  `MEYAAR_DATABASE_URL=postgresql+psycopg2://postgres@<host-ip>:5432/meyaar_db`
  and ensure that container publishes 5432 (it does: `-p 5432:5432`).

## 6. Sanity checks

```bash
MEYAAR_ALLOW_LLM=false agent/.venv/bin/python -m pytest agent/tests -q   # 63 passed, no DB needed
docker exec meyaar-postgis pg_isready -U postgres -h localhost           # DB up
```

## 7. Common errors

| symptom | fix |
|---|---|
| chat says "requires an LLM key" | set MEYAAR_LLM_API_KEY in agent/.env; `unset MEYAAR_ALLOW_LLM` |
| analyze says fetch/DB failure | PostGIS not running or wrong MEYAAR_DATABASE_URL |
| container "gone" | `docker context use colima` (macOS) |
| UI Analyze → 404 no results | that run has no validation_results; generate one with live_test.sh |
| mic says not supported | open via localhost or HTTPS (secure context) |
