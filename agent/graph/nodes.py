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
    for r in g.items:
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
        "\n\nReply STRICT JSON only: an array of objects with keys "
        '["result_id", "status", "explanation", "cause", "recommendation", '
        '"human_review_required", "related_features"]. '
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

    return {"analyses": analyses, "trace": trace, "errors": errors}


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


# ── summarize ───────────────────────────────────────────────────────────────
def summarize(state: AgentState, config: Optional[RunnableConfig] = None) -> dict:
    repo = get_repository(config)
    summary = repo.build_summary(state.results, state.analyses)
    summary["priority_actions"] = repo.priority_actions(summary)
    trace = state.trace + [f"[summarize] {summary['total_errors']} error(s), "
                           f"{summary['analyzed']} analyzed"]
    return {"summary": summary, "trace": trace}
