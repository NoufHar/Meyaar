# Remediation & Spatial Measurements — Agent Extension

Trainer-requested extension of the Meyaar Error Analysis Agent
(agentic role, `agent/`).

**Principle kept throughout:**
> The LLM interprets and proposes; deterministic application code verifies
> and executes.

Two capabilities were added on top of the existing LangGraph + Repository +
PostGIS + rule-registry architecture (no redesign):

1. **Information-retrieval tool** — `get_spatial_measurements`
2. **Remediation capability** — automatic fix when safe & deterministic,
   human-review escalation otherwise, with full provenance/audit.

---

## 1. Architecture change

Graph flow (existing path preserved for clean runs):

```
 START -> load -> (no results) -----------------------------> summarize -> END
 START -> load -> prepare -> analyze -> validate -> remediate -> save -> summarize -> END
                                                  │
                 LLM advisory remediation_intent ──┤ (never decides)
                                                  ▼
        agent/remediation/service.py  (deterministic policy)
                  │
      ┌───────────┼────────────────┐
      ▼           ▼                ▼
   auto_fix    human_review      no_action
      │           │                │
   repo.apply_  audit row:        audit row:
   geometry_    status            status
   repair()     pending_review    none
   (txn,        (recommended
   rollback)    action kept)
      ▼
  save (analyses + audit) -> summarize -> END
```

New files:
- `agent/remediation/__init__.py`
- `agent/remediation/service.py`  — `decide()` + policy enforcement
- `agent/remediation/policy.py`   — `auto_fix_allowed()` / `IMPLEMENTED_OPS`
- `agent/schema/agent_remediation_actions.sql` — audit table DDL

Changed files (existing code extended, nothing redesigned):
- `agent/core/models.py`          — `RuleDefinition` remediation fields;
                                  `RemediationDecision`, `RemediationRecord`,
                                  `RemediationListResponse`
- `agent/rules/registry.json`     — per-rule remediation policy
- `agent/db/base.py`              — Repository interface: measurements,
                                  `apply_geometry_repair`,
                                  `save/fetch_remediation_records`;
                                  `RemediationError`
- `agent/db/postgres.py`          — PostGIS implementations (see §5)
- `agent/db/memory.py`            — in-memory double (tests/demos)
- `agent/tools/__init__.py`       — `get_spatial_measurements` tool
- `agent/graph/state.py`          — `remediation_intents`, `remediation`
- `agent/graph/nodes.py`          — intent capture + `remediate` node
- `agent/graph/builder.py`        — `remediate` between validate and save
- `agent/api/router.py`           — GET `.../remediation` endpoint

## 2. New tool — `get_spatial_measurements`

Signature (registry entry `get_spatial_measurements`):

    get_spatial_measurements(repo, layer_name, feature_id,
                             other_feature_id=None) -> dict | None

Returns structured facts **computed by PostGIS** (never invented):
`feature_id`, `geometry_type`, `srid`, `is_valid`, `is_empty`, `length_m`
(lines, geography metres), `area_m2` (polygons), `vertex_count`, `centroid`,
`bbox`. When `other_feature_id` is supplied, relationship facts are added:
`distance_m`, `intersects`, `overlap_area_m2`. Inapplicable values are
`None`; a missing feature returns `None` (never fabricated). All reads go
through the existing `Repository` abstraction over the read-only engine —
`query_postgis_readonly` remains a fallback for advanced queries.

Tool registry now: `get_validation_results`, `get_feature_context`,
`get_related_features`, `query_postgis_readonly`, `get_spatial_measurements`,
`get_rule_definition`.

## 3. Remediation policy (rules/registry.json — source of truth)

Each of the 13 rules declares `remediation_type`, `auto_fix_allowed`,
`remediation_description`. Summary:

| Rule | remediation_type | auto_fix_allowed | Outcome |
|---|---|---|---|
| BLD001 overlap | human_review | no | review (which footprint is authoritative) |
| BLD002 dup buildings | human_review | no | review (destructive merge) |
| **BLD003 invalid geometry** | **geometry_repair** | **yes** | **auto-fix (ST_MakeValid)** |
| BLD004 missing geometry | human_review | no | review (never invent geometry) |
| RD001 overshoot (heuristic) | human_review | no | review — REQUIRED |
| RD002 undershoot (heuristic) | human_review | no | review — REQUIRED |
| RD003 dup roads | human_review | no | review |
| **RD004 invalid geometry** | **geometry_repair** | **yes** | **auto-fix (ST_MakeValid)** |
| RD005 missing geometry | human_review | no | review |
| GIS001 CRS | crs_transform | no | review (confirm target EPSG) |
| GIS002 coordinates | human_review | no | review (confirm source CRS) |
| GIS003–005 attributes | attribute_correction | no | review (values need a source) |

The LLM cannot override any of this — `agent/remediation/service.py` decides
purely from the registry + the validated analysis, and only `geometry_repair`
is in `IMPLEMENTED_OPS`, so an auto-fix can only ever run for BLD003/RD004.

## 4. Decision model

`RemediationDecision` (pydantic, validated):

    result_id, action: auto_fix|human_review|no_action,
    remediation_type, reason, confidence, proposed_changes,
    human_review_required

Decision ladder (deterministic):
1. rule unknown / informational  -> `no_action`
2. insufficient context          -> `human_review` (no invention)
3. heuristic (RD001/RD002)        -> `human_review` (always)
4. registry auto + confirmed + feature exists -> `auto_fix`
5. registry auto but feature missing         -> `human_review`
6. layer-level issue (no feature)            -> `no_action` (guidance kept)
7. otherwise deterministic not auto-fixable  -> `human_review`

If the LLM sends a `remediation_intent`, it is validated: an invalid action
is ignored, and any claim that overrides the registry (e.g. "auto-fix RD001")
is rejected — the reason field records the override. This is enforced both at
the service level (unit tests) and through the graph.

## 5. Database safety & audit (Part 8 + 9)

- All reads stay on the existing read-only engine + SQL guard.
- The only source-table mutation is the whitelisted, parameterized
  `Repository.apply_geometry_repair(layer, feature_id)`:
  - single transaction (`engine.begin()`, rollback on any error),
  - guards: feature must exist, geometry not NULL, currently invalid,
  - applies `ST_MakeValid`; a single-part Multi result is collapsed so it
    stays storable in `Polygon`/`LineString` typed columns; multi-part
    results that would change the column type are refused with a clear
    `RemediationError` (rolled back, recorded `failed`, human re-digitization
    flagged),
  - returns before/after GeoJSON snapshots for the audit row.
- New table `public.agent_remediation_actions` (DDL in
  `agent/schema/agent_remediation_actions.sql`), one row per
  `(run_id, result_id)`, unique upsert (idempotent re-runs):

      remediation_id, run_id, result_id, layer_name, feature_id, rule_id,
      action (auto_fix|human_review|no_action),
      remediation_type, status (applied|failed|pending_review|none),
      issue, reason, recommended_action,
      before_state JSONB, after_state JSONB,
      agent_model, human_review_required, executed_at

Dashboard distinction:
- `auto_fix` + `applied`            -> automatically fixed
- `human_review` + `pending_review` -> queued for a reviewer
- `no_action` + `none`              -> nothing to do (guidance kept)
- `auto_fix` + `failed`             -> execution failed, rolled back, logged

## 6. API

New endpoint (existing auth applies):

    GET /api/validation/{run_id}/remediation
    -> {run_id, remediation: [RemediationRecord, ...]}

`POST /api/validation/{run_id}/analyze` now runs analysis AND remediation in
one pass, so the dashboard can read both `/analysis` and `/remediation` after
a single call. `agent/api/openapi.json` is regenerated (4 paths).

The chat endpoint is remediation-aware: its context includes the audit
summary/items, so it answers "what was fixed automatically / what needs a
human?" truthfully from the records. A separate, related feature persists a
per-run executive narrative (`public.agent_run_summaries`, returned as
`summary.narrative` on GET `/analysis`) — both are documented in
`agent/docs/INTEGRATION.md`.

## 7. Tests (96 passing, no DB / no LLM required)

New: `agent/tests/test_measurements.py`, `agent/tests/test_remediation.py`;
extended: `test_tools.py` (registry), `test_api.py` (endpoint).

Trainer scenario coverage:
1. Building invalid geometry -> measurements available -> auto-fix applied
   (BD003, in-memory repair recorded; real PostGIS verified live)
2. RD001 road overshoot -> heuristic -> human review (auto rejected)
3. RD002 road undershoot -> human review
4. Missing geometry -> never invented -> human review
5. LLM invalid remediation action -> deterministic validator rejects it
6. LLM claims heuristic is auto-fixable -> system overrides -> human review
7. Remediation SQL failure -> recorded `failed` (rollback simulated; other
   fixes continue)
8. LLM disabled -> template path remediates deterministically (exact policy
   mapping asserted)
9. No validation errors -> clean path preserved (load -> summarize, no
   `[remediate]` trace, empty records)

Run: `MEYAAR_ALLOW_LLM=false agent/.venv/bin/python -m pytest agent/tests -q`

## 8. Example end-to-end flows

(a) Safely auto-fixable (invalid building geometry, BLD003):
    engine flags `BLD_303` invalid -> prepare fetches context ->
    analyze: confirmed -> remediate: registry says geometry_repair +
    auto_fix_allowed -> `apply_geometry_repair` runs ST_MakeValid in a
    transaction -> record {action: auto_fix, status: applied,
    before/after GeoJSON} -> geometry now ST_IsValid = true.

(b) Human-review (road overshoot, RD001):
    engine flags `RD_101` (5 m tolerance heuristic) -> analysis:
    candidate + human_review_required -> remediate: heuristic => always
    human_review (even if the LLM suggested auto-fix) -> record {action:
    human_review, status: pending_review, recommended_action: "trim only
    after visual confirmation"} -> dashboard review queue.

(c) Clean run:
    no validation_results -> load routes straight to summarize -> zero
    summary, no analyses, no remediation records, no DB writes.

## 9. Assumptions & limitations

- Only `geometry_repair` is implemented as an executable operation. The
  registry marks attribute/CRS ops as policy types but `auto_fix_allowed`
  stays false until those repository methods exist (removing a road or
  merging duplicates is intentionally NOT auto-executed — destructive).
- A repair whose valid output changes geometry type (e.g. bowtie polygon ->
  2-part MultiPolygon vs a `Polygon`-typed column) is refused and recorded
  `failed` with a human-re-digitization note — verified live.
- Remediation mutates the *source layer feature* (roads/buildings) — on the
  team's dev DB this is intended; the audit table is the trace. Full
  production rollout needs the team's decision on who runs repairs.
- GIS rules were not exercisable live (config tables empty); policy tested at
  registry/unit level.
- Agent tests stub auth/DB as before; the trainer scenarios are covered
  hermetically and the live DB smoke was verified separately.
