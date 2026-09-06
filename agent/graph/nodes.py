"""LangGraph nodes for the Error Analysis Agent.

Nodes follow the dual-path pattern: an LLM path (when a key is configured)
and a deterministic template path (CI/test safe, same output schema).
The template path never invents numbers, locations, or feature ids — it only
echoes rule-engine details and registry text.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from langchain_core.runnables import RunnableConfig

from agent.core.config import settings
from agent.core.models import ErrorAnalysis, ValidationResult
from agent.db.base import Repository
from agent.db.postgres import PostgresRepository
from agent.graph.state import AgentState, PreparedGroup
from agent.rules.registry import get_rule
from agent.tools import get_rule_definition

logger = logging.getLogger(__name__)

MAX_LLM_ITEMS_PER_GROUP = 25

_ID_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9_])([A-Za-z_]{2,}[0-9]{2,})")


def get_repository(config: Optional[RunnableConfig]) -> Repository:
    """Repository from graph config; falls back to Postgres."""
    if config:
        repo = config.get("configurable", {}).get("repository")
        if repo is not None:
            return repo
    return PostgresRepository()


def get_llm_from(config: Optional[RunnableConfig]):
    if config:
        llm = config.get("configurable", {}).get("llm")
        if llm is not None:
            return llm
    from agent.core.llm import get_llm
    return get_llm()


def _trace(state: AgentState, *entries: str) -> list:
    return state.trace + [f"[{entries[0]}] {entries[1]}" if len(entries) == 2 else entries[0]]


# ── load ────────────────────────────────────────────────────────────────────
def load_results(state: AgentState, config: Optional[RunnableConfig] = None) -> dict:
    repo = get_repository(config)
    try:
        results = repo.fetch_results(state.run_id)
    except Exception as exc:
        logger.exception("fetch_results failed for run %s", state.run_id)
        return {"results": [], "errors": state.errors + [f"db.fetch_results: {exc}"],
                "trace": _trace(state, "load", f"DB failure: {exc}")}
    return {"results": results,
            "trace": _trace(state, "load", f"{len(results)} result(s) for run {state.run_id}")}


def route_after_load(state: AgentState) -> str:
    return "prepare" if state.results else "summarize"
_ID_TOKEN_RE = re.compile(
    # identifier-like tokens only: underscore-separated words or alphanumeric
    # ids (BLD_INJ_B, BLD_157, BLDG_0538831, RD_101) — NOT plain words
    # ("Building") or bare numbers ("28.04", "m²").
    r"(?<![A-Za-z0-9_])([A-Za-z]+_[A-Za-z0-9_]+|[A-Za-z]+[0-9][A-Za-z0-9_]*)")


def _parse_related_ids(details: Optional[str], own_id: Optional[str],
                       available: Optional[set] = None) -> list[str]:
    """Grounded only: ids mentioned in the rule-engine details text that we
    can verify exist in the retrieved context. Never invents an id."""
    if not details:
        return []
    ids = [m for m in _ID_TOKEN_RE.findall(details)]
    if own_id and own_id in ids:
        ids.remove(own_id)
    if available is not None:
        ids = [i for i in ids if i in available]   # existence-checked
    seen = set()
    out = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def _related_for(g: PreparedGroup, r: ValidationResult) -> list[str]:
    """Parsed related ids, filtered to ids whose context we actually have."""
    return _parse_related_ids(r.details, r.feature_id, set(g.contexts))


def prepare_groups(state: AgentState, config: Optional[RunnableConfig] = None) -> dict:
    repo = get_repository(config)
    groups: dict[tuple, PreparedGroup] = {}
    for r in state.results:
        key = (r.layer_name, r.rule_id)
        if key not in groups:
            groups[key] = PreparedGroup(layer_name=r.layer_name, rule_id=r.rule_id,
                                        rule=get_rule_definition(r.rule_id))
        groups[key].items.append(r)

    # Bulk context retrieval once per (layer) for all referenced feature ids.
    for g in groups.values():
        layer = g.layer_name
        ids: list[str] = []
        for r in g.items:
            if r.feature_id:
                ids.append(r.feature_id)
            ids.extend(_parse_related_ids(r.details, r.feature_id))
        try:
            g.contexts = repo.fetch_related_features(layer, list(dict.fromkeys(ids)))
        except Exception as exc:  # tool failure must not kill the run
            logger.exception("context retrieval failed for %s/%s", layer, g.rule_id)
            g.contexts = {}
            state.errors.append(f"context.{g.rule_id}: {exc}")

    ordered = [groups[k] for k in
               sorted(groups, key=lambda k: (k[0], k[1]))]
    trace = state.trace + [f"[prepare] {len(ordered)} group(s), "
                           f"{sum(len(g.items) for g in ordered)} error(s)"]
    return {"groups": ordered, "trace": trace}


# ── template analysis (deterministic fallback / repair) ─────────────────────
def _base_status(rule_id: str, rule: Optional[dict]) -> tuple[str, bool]:
    """(status, human_review_required) before any LLM involvement."""
    if rule is None:
        return "informational", False
    if rule.get("type") == "heuristic":
        return "candidate", True
    return "confirmed", bool(rule.get("requires_human_review"))


def template_analysis(r: ValidationResult, rule: Optional[dict],
                      context: Optional[dict], related_ids: list[str]) -> ErrorAnalysis:
    """Deterministic analysis for one result. Grounded, no invented facts."""
    rule_id, etype = r.rule_id, r.error_type
    has_info = bool((r.details or "").strip() or context)
    status, human = _base_status(rule_id, rule)
    if not has_info and rule is not None and rule.get("type") != "heuristic":
        status = "insufficient_context"  # cannot explain without source info

    explanation_parts = []
    if not has_info:
        explanation_parts.append(
            f"{etype} reported for {r.layer_name} feature {r.feature_id or '(unknown)'} "
            f"by rule {rule_id}, but no details or feature context were available "
            "to explain it.")
    else:
        explanation_parts.append(
            f"{etype} detected on {r.layer_name} feature {r.feature_id or '(unknown)'} "
            f"by PostGIS rule {rule_id} (severity: {r.severity}).")
        if r.details:
            explanation_parts.append(f"Rule engine details: {r.details.strip()}")
    if context:
        explanation_parts.append(
            f"Feature context: {context.get('geometry_type', 'unknown geometry')}, "
            f"SRID {context.get('srid', '?')}, centroid {context.get('centroid', 'n/a')}.")
    if status == "candidate":
        explanation_parts.append(
            "Heuristic topology candidate (5 m tolerance) — requires human review "
            "before it is treated as a confirmed error.")
    if not has_info:
        explanation_parts.append(
            "Insufficient context: no rule-engine details or feature record were "
            "available, so this analysis cannot be more specific.")
    explanation = " ".join(p for p in explanation_parts if p).strip()

    cause = None
    if rule:
        cause = f"Rule {rule_id} ({rule.get('name', etype)}): {rule.get('description', '')}"
        if status == "candidate":
            cause += " The check is heuristic, so this may be a false positive."
    recommendation = rule.get("recommendation") if rule else None
    if status == "candidate" and recommendation:
        recommendation += " If the candidate is confirmed as a non-issue, mark it as a false positive."

    return ErrorAnalysis(
        result_id=r.result_id, run_id=r.run_id, layer_name=r.layer_name,
        feature_id=r.feature_id, rule_id=rule_id, error_type=etype,
        severity=r.severity, status=status, explanation=explanation,
        cause=cause, recommendation=recommendation,
        human_review_required=human,
        related_features=related_ids,
        insufficient_context=(not has_info or status == "insufficient_context"),
        agent_model="template-fallback",
    )


def _code_fence_strip(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1]
        t = t.rsplit("\n", 1)[0] if t.endswith("```") else t
        if t.endswith("```"):
            t = t[:-3].strip()
    return t.strip()


def _repair_analysis(raw: dict, r: ValidationResult, rule: Optional[dict],
                     context: Optional[dict] = None) -> ErrorAnalysis:
    """Coerce a (possibly malformed) LLM dict into a valid ErrorAnalysis.

    Invariants (LLM cannot override these):
      * heuristic rules -> status candidate + human review True
      * deterministic rule WITH source info (details or context) -> confirmed
      * deterministic rule WITHOUT any source info -> insufficient_context
      * deterministic rules never get human_review_required from the LLM
    """
    status = str(raw.get("status", "")).strip().lower()
    valid_status = {"confirmed", "candidate", "informational", "insufficient_context"}
    if status not in valid_status:
        status = "confirmed"
    has_info = bool((r.details or "").strip() or context)

    llm_marked_insufficient = status == "insufficient_context"
    if rule is None:
        status = "informational"
    elif rule.get("type") == "heuristic":
        status = "candidate"
    elif not has_info:
        status = "insufficient_context"
    else:
        status = "confirmed"
        if llm_marked_insufficient:
            # LLM claimed insufficient context, but engine details/context
            # exist — trust the source data, not the model's guess.
            tmpl = template_analysis(r, rule, context,
                                     [str(x) for x in (raw.get("related_features") or [])])
            return tmpl

    human = status == "candidate"
    if status == "confirmed" and rule is not None:
        human = bool(rule.get("requires_human_review"))   # registry decides
    explanation = str(raw.get("explanation", "")).strip() or \
        template_analysis(r, rule, context, []).explanation
    return ErrorAnalysis(
        result_id=r.result_id, run_id=r.run_id, layer_name=r.layer_name,
        feature_id=r.feature_id, rule_id=r.rule_id, error_type=r.error_type,
        severity=r.severity, status=status, explanation=explanation,
        cause=str(raw["cause"]).strip() if raw.get("cause") else None,
        recommendation=str(raw["recommendation"]).strip() if raw.get("recommendation") else None,
        human_review_required=human,
        related_features=[str(x) for x in (raw.get("related_features") or [])],
        insufficient_context=bool(raw.get("insufficient_context")) or status == "insufficient_context",
        agent_model=settings.agent_model,
    )


# ── analyze (LLM path per group with template fallback) ─────────────────────
def _group_prompt(g: PreparedGroup) -> str:
    rule_txt = json.dumps(g.rule, ensure_ascii=False) if g.rule else "UNKNOWN RULE"
    items = []
    for r in g.items[:MAX_LLM_ITEMS_PER_GROUP]:
        ctx = g.contexts.get(r.feature_id)
        related = {fid: g.contexts.get(fid) for fid in _related_for(g, r)}
        items.append({
            "result_id": r.result_id, "feature_id": r.feature_id,
            "severity": r.severity, "details": r.details,
            "feature_context": ctx, "related_features_context": related,
        })
    return (
        "You are Meyaar's error-analysis agent for Saudi geospatial compliance. "
        "The PostGIS rule engine ALREADY detected these errors — you interpret, "
        "explain, and recommend. Never invent feature ids, locations, distances, "
        "or areas. Use ONLY the details and context below. If a feature has no "
        "context and details are empty, set status insufficient_context.\n"
        f"Rule definition: {rule_txt}\n"
        f"Layer: {g.layer_name}\n"
        "Errors (JSON): " + json.dumps(items, ensure_ascii=False) +
        "Reply STRICT JSON only: an array of objects with keys "
        '["result_id", "status", "explanation", "cause", "recommendation", '
        '"human_review_required", "related_features", '
        '"remediation_intent"(optional)]. '
        '"remediation_intent" is ADVISORY ONLY: an object {"action": '
        '"auto_fix"|"human_review"|"no_action", "reason": "..."}. A '
        "deterministic policy layer validates it against the rule registry — "
        "your suggestion can never override the policy (heuristic rules are "
        "always human_review). "
        "Heuristic rules (type=heuristic) MUST be status 'candidate' with "
        "human_review_required=true. Keep explanations grounded in the data."
    )


def _analyze_group_llm(g: PreparedGroup, llm) -> Optional[list[dict]]:
    prompt = _group_prompt(g)
    attempts = max(1, settings.llm_retries)
    for attempt in range(attempts):
        try:
            resp = llm.invoke(prompt)
            payload = json.loads(_code_fence_strip(str(resp.content)))
            if isinstance(payload, dict):  # tolerate {"analyses": [...]}
                payload = payload.get("analyses", payload)
            if not isinstance(payload, list):
                raise ValueError("LLM did not return an array")
            return payload
        except Exception as exc:
            logger.warning("LLM group analysis attempt %d/%d failed: %s",
                           attempt + 1, attempts, exc)
    return None


def analyze(state: AgentState, config: Optional[RunnableConfig] = None) -> dict:
    llm = get_llm_from(config)
    analyses: list[ErrorAnalysis] = []
    remediation_intents: dict[int, dict] = {}
    trace = list(state.trace)
    errors = list(state.errors)

    for g in state.groups:
        rule = g.rule
        llm_rows: Optional[list[dict]] = None
        if llm is not None and rule is not None:
            llm_rows = _analyze_group_llm(g, llm)
        if llm_rows is not None:
            before = len(analyses)
            by_result = {r.result_id: r for r in g.items}
            for raw in llm_rows:
                rid = raw.get("result_id")
                r = by_result.get(rid)
                if r is None:
                    continue  # LLM invented a result_id -> drop silently
                # Advisory remediation intent (validated later by policy).
                intent = raw.get("remediation_intent")
                if isinstance(intent, dict):
                    remediation_intents[rid] = intent
                analyses.append(_repair_analysis(raw, r, rule,
                                                 g.contexts.get(r.feature_id)))
            # any item the LLM skipped -> template fallback for that item
            done = {a.result_id for a in analyses}
            for r in g.items:
                if r.result_id not in done:
                    analyses.append(template_analysis(
                        r, rule, g.contexts.get(r.feature_id), _related_for(g, r)))
            src = "llm" if len(analyses) > before else "llm-fallback"
        else:
            for r in g.items:
                analyses.append(template_analysis(
                    r, rule, g.contexts.get(r.feature_id), _related_for(g, r)))
            src = "llm-fallback" if llm is not None else "template"
        trace.append(f"[analyze] {g.rule_id}: {src} ({len(g.items)} errors)")

    return {"analyses": analyses, "remediation_intents": remediation_intents,
            "trace": trace, "errors": errors}


# ── validate output ─────────────────────────────────────────────────────────
def validate_output(state: AgentState, config: Optional[RunnableConfig] = None) -> dict:
    results = {r.result_id: r for r in state.results}
    # context per result_id (from prepared groups) for the repair invariants
    ctx_by_id = {}
    for g in state.groups:
        for item in g.items:
            ctx_by_id[item.result_id] = g.contexts.get(item.feature_id)
    fixed: list[ErrorAnalysis] = []
    for a in state.analyses:
        r = results.get(a.result_id)
        if r is None:
            fixed.append(a)   # nothing to validate against — keep as-is
            continue
        rule = get_rule(a.rule_id)
        repaired = _repair_analysis(a.model_dump(), r,
                                    rule.model_dump() if rule else None,
                                    ctx_by_id.get(a.result_id))
        fixed.append(repaired)
    bad = [a for a in state.analyses if a.status not in
           {"confirmed", "candidate", "informational", "insufficient_context"}]
    trace = state.trace + [f"[validate] {len(fixed)} analysis(es) conform to schema"
                           + (f"; repaired {len(bad)} malformed" if bad else "")]
    return {"analyses": fixed, "trace": trace}


# ── save ────────────────────────────────────────────────────────────────────
def save_analyses(state: AgentState, config: Optional[RunnableConfig] = None) -> dict:
    repo = get_repository(config)
    if not state.analyses:
        return {"trace": _trace(state, "save", "nothing to save")}
    try:
        saved = repo.save_analyses(state.analyses)
        return {"trace": _trace(state, "save", f"saved {saved} analysis row(s)")}
    except Exception as exc:
        logger.exception("save_analyses failed")
        return {"errors": state.errors + [f"db.save_analyses: {exc}"],
                "trace": _trace(state, "save", f"DB failure: {exc}")}


# ── summarize (incl. executive narrative, persisted per run) ────────────────
def _remediation_counts(state: AgentState) -> dict:
    recs = state.remediation or []
    return {
        "total": len(recs),
        "auto_fixed": sum(1 for r in recs
                          if r.get("action") == "auto_fix"
                          and r.get("status") == "applied"),
        "failed": sum(1 for r in recs if r.get("status") == "failed"),
        "pending_review": sum(1 for r in recs
                              if r.get("action") == "human_review"
                              and r.get("status") == "pending_review"),
        "no_action": sum(1 for r in recs if r.get("action") == "no_action"),
    }


def _findings_rows(summary: dict) -> list[dict]:
    """counts_by_rule enriched with registry names/severity/layer, ordered by
    severity (critical first), then name. Unknown rule ids keep the raw id."""
    by_rule = summary.get("counts_by_rule") or {}
    sev_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    rows = []
    for rid, count in by_rule.items():
        rd = get_rule(rid)
        rows.append({
            "rule_id": rid,
            "count": count,
            "name": rd.error_type if rd else rid,
            "layer": (rd.layer if rd else "") or "",
            "severity": rd.baseline_severity if rd else "low",
        })
    rows.sort(key=lambda x: (sev_rank.get(x["severity"], 3),
                             x["name"].lower()))
    return rows


def _findings_text(summary: dict) -> str:
    rows = _findings_rows(summary)
    if not rows:
        return ""
    parts = []
    for row in rows:
        qual = (f" ({row['layer']})"
                if row["layer"] and row["layer"] != "general" else "")
        parts.append(f"{row['count']} {row['name']}{qual}")
    return "Findings: " + ", ".join(parts) + "."


def _template_narrative(state: AgentState, summary: dict,
                        rem: dict) -> str:
    """Deterministic executive summary (no LLM needed)."""
    run_id = state.run_id
    total = summary.get("total_errors", 0)
    if total == 0:
        return (f"Validation run {run_id} found no errors; "
                "no agent remediation was required.")
    parts = []
    sev = ", ".join(f"{summary.get(k + '_errors', 0)} {k}"
                    for k in ("critical", "high", "medium", "low")
                    if summary.get(k + "_errors"))
    parts.append(f"Validation run {run_id} reported {total} error(s) "
                 f"({sev}).")
    if summary.get("most_common_error"):
        parts.append(f"The most common issue was "
                     f"{summary['most_common_error'].lower()}.")
    findings = _findings_text(summary)
    if findings:
        parts.append(findings)
    parts.append(f"The agent analyzed {summary.get('analyzed', 0)} result(s).")
    if rem.get("total"):
        parts.append(
            f"Remediation: {rem['auto_fixed']} automatically fixed "
            f"(geometry repair), {rem['failed']} repair attempt(s) failed and "
            f"were rolled back, {rem['pending_review']} queued for human "
            f"review, {rem['no_action']} required no action.")
    if summary.get("priority_actions"):
        parts.append("Priority: " + summary["priority_actions"][0].lower() + ".")
    return " ".join(parts)


def _llm_narrative(state: AgentState, summary: dict, rem: dict,
                   llm) -> Optional[str]:
    """One LLM call per run for a grounded executive narrative. Falls back to
    the template (caller) on any failure — never fabricates numbers."""
    payload = {
        "run_id": state.run_id,
        "total_errors": summary.get("total_errors", 0),
        "severity": {"critical": summary.get("critical_errors", 0),
                     "high": summary.get("high_errors", 0),
                     "medium": summary.get("medium_errors", 0),
                     "low": summary.get("low_errors", 0)},
        "findings_by_rule": _findings_rows(summary),
        "counts_by_layer": summary.get("counts_by_layer", {}),
        "most_common_error": summary.get("most_common_error"),
        "remediation": rem,
        "priority_actions": summary.get("priority_actions", [])[:3],
    }
    prompt = (
        "You are Meyaar's reporting assistant. Write a concise executive "
        "summary (3-6 sentences) of this geospatial quality validation run "
        "for a technical team. Ground EVERY statement in the JSON provided — "
        "never invent error counts, feature ids, areas, distances, or rule "
        "meanings. Mention the severity distribution, list each distinct "
        "error group from 'findings_by_rule' with its count (e.g. 'two "
        "duplicate buildings, one missing geometry'), say which group is the "
        "most common or most important, and give the remediation outcome "
        "(how many errors were auto-fixed, how many need human review, how "
        "many had no action). Plain prose, no markdown, no technical ids.\n\n"
        "Run facts (JSON): " + json.dumps(payload, ensure_ascii=False)
    )
    attempts = max(1, settings.llm_retries)
    for attempt in range(attempts):
        try:
            resp = llm.invoke(prompt)
            text = _code_fence_strip(str(resp.content)).strip()
            looks_like_json = text[:1] in ("{", "[")
            if looks_like_json:
                json.loads(text)   # raises -> not JSON, fine
                continue           # structured JSON is NOT a narrative
            if len(text) >= 40:
                return text
        except Exception as exc:
            logger.warning("narrative attempt %d/%d failed: %s",
                           attempt + 1, attempts, exc)
    return None


def summarize(state: AgentState, config: Optional[RunnableConfig] = None) -> dict:
    repo = get_repository(config)
    summary = repo.build_summary(state.results, state.analyses)
    summary["priority_actions"] = repo.priority_actions(summary)
    rem = _remediation_counts(state)

    llm = get_llm_from(config)
    narrative: Optional[str] = None
    if llm is not None and summary.get("total_errors", 0) > 0:
        narrative = _llm_narrative(state, summary, rem, llm)
    if not narrative:
        narrative = _template_narrative(state, summary, rem)
    summary["narrative"] = narrative
    summary["remediation"] = rem

    errors = list(state.errors)
    try:
        repo.save_run_summary(
            state.run_id, narrative,
            agent_model=settings.agent_model,
            counts={"errors": {k: summary.get(k, 0) for k in
                               ("total_errors", "critical_errors",
                                "high_errors", "medium_errors", "low_errors",
                                "analyzed")},
                    "by_rule": summary.get("counts_by_rule", {}),
                    "by_layer": summary.get("counts_by_layer", {}),
                    "remediation": rem})
    except Exception as exc:
        logger.exception("save_run_summary failed for run %s", state.run_id)
        errors.append(f"db.save_run_summary: {exc}")

    trace = state.trace + [f"[summarize] {summary['total_errors']} error(s), "
                           f"{summary['analyzed']} analyzed; narrative "
                           f"{'saved' if not errors else 'logged'}"
                           f" (model={settings.agent_model})"]
    return {"summary": summary, "errors": errors, "trace": trace}


# ── remediate (deterministic policy + whitelisted execution) ────────────────
def _issue_text(r: ValidationResult, a: ErrorAnalysis) -> str:
    if r.details:
        detail = str(r.details).strip().replace("\n", " ")
        return f"{a.error_type}: {detail[:240]}"
    return a.error_type


def remediate(state: AgentState, config: Optional[RunnableConfig] = None) -> dict:
    """Decide remediation for every analyzed result and execute approved
    auto-fixes. Runs AFTER validate_output and BEFORE save so both the
    analyses and the remediation audit land in the same run.

    Trust boundary: decisions come from agent/remediation/service.py which
    reads the rule registry — the LLM's remediation_intent is advisory only
    and can never override policy. Execution goes through ONE whitelisted
    repository method (apply_geometry_repair); any failure is recorded as
    status=failed (transaction rolled back by the repository).
    """
    from agent.remediation.service import decide

    repo = get_repository(config)
    if not state.analyses:
        return {"remediation": [],
                "trace": _trace(state, "remediate", "no analyses — nothing to remediate")}
    results = {r.result_id: r for r in state.results}
    records: list[dict] = []
    errors = list(state.errors)

    for a in state.analyses:
        r = results.get(a.result_id)
        if r is None:
            continue
        rule = get_rule(a.rule_id)
        rule_dict = rule.model_dump() if rule else None

        feature_available = False
        if a.feature_id:
            try:
                feature_available = (repo.fetch_feature_context(
                    a.layer_name, a.feature_id) is not None)
            except Exception:
                feature_available = False

        decision = decide(r, a, rule_dict,
                          llm_intent=state.remediation_intents.get(a.result_id),
                          feature_available=feature_available)

        rec = {
            "run_id": a.run_id, "result_id": a.result_id,
            "layer_name": a.layer_name, "feature_id": a.feature_id,
            "rule_id": a.rule_id,
            "action": decision.action,
            "remediation_type": decision.remediation_type,
            "status": "none",
            "issue": _issue_text(r, a),
            "reason": decision.reason,
            "recommended_action": ((rule_dict or {}).get("recommendation")
                                   or a.recommendation),
            "before_state": {}, "after_state": {},
            "agent_model": a.agent_model,
            "human_review_required": decision.human_review_required,
        }

        if decision.action == "auto_fix":
            try:
                outcome = repo.apply_geometry_repair(a.layer_name, a.feature_id)
                rec["status"] = "applied"
                rec["before_state"] = outcome.get("before", {}) or {}
                rec["after_state"] = outcome.get("after", {}) or {}
                if not outcome.get("changed", True):
                    rec["reason"] += (" Feature geometry already valid — "
                                      "no change needed.")
            except Exception as exc:
                rec["status"] = "failed"
                rec["reason"] = (f"{rec['reason']} Execution failed and was "
                                 f"rolled back: {exc}")
                errors.append(f"remediation.{a.rule_id}/{a.result_id}: {exc}")
        elif decision.action == "human_review":
            rec["status"] = "pending_review"
        records.append(rec)

    saved = 0
    try:
        saved = repo.save_remediation_records(records)
    except Exception as exc:
        logger.exception("save_remediation_records failed for run %s",
                         state.run_id)
        errors.append(f"db.save_remediation_records: {exc}")

    applied = sum(1 for x in records if x["status"] == "applied")
    pending = sum(1 for x in records if x["action"] == "human_review")
    none = sum(1 for x in records if x["action"] == "no_action")
    failed = sum(1 for x in records if x["status"] == "failed")
    trace = _trace(
        state, "remediate",
        f"{len(records)} decision(s): {applied} auto-fixed, {pending} "
        f"human-review, {none} no-action, {failed} failed"
        + (f"; persisted {saved}" if saved else ""))
    return {"remediation": records, "errors": errors, "trace": trace}
