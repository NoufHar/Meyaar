"""Grounded chat over a run's validation results, agent analyses and the
remediation audit.

The chat answers questions about ONE engine run using ONLY:
  - the run summary (counts, most common error, priority actions)
  - the stored agent analyses (explanations, causes, recommendations)
  - the rule registry (rule meaning, heuristic vs deterministic)
  - the remediation audit (what was auto-fixed, what is queued for a human,
    what failed) — so "what did the agent fix?" is answered truthfully.

It never answers from general knowledge about features that are not in the
run, and it never invents numbers. Sources returned are filtered to ids that
actually exist in the provided context (no hallucinated citations).
"""
from __future__ import annotations

import json
from typing import Any, Optional

from agent.core.config import settings
from agent.core.llm import get_llm
from agent.db.base import Repository
from agent.rules.registry import get_rule

SYSTEM_PROMPT = (
    "You are Meyaar's chat assistant for a Saudi geospatial compliance run. "
    "Answer questions about THIS validation run using ONLY the context provided "
    "(run summary + per-error analyses + remediation audit). Rules: "
    "1) Never invent feature ids, counts, areas, or distances. "
    "2) If the question is about something not present in the context, say so "
    "   explicitly (e.g. 'that feature is not among this run's findings'). "
    "3) Be concise and practical. Group findings by error type and severity, "
    "and state the count in each group. Present individual findings as "
    "'the first error', 'the second error', and so on. Do not include file "
    "names, UUIDs, feature IDs, result IDs, or rule IDs in the visible answer "
    "unless the user explicitly asks for technical identifiers or exact details. "
    "4) Heuristic rules (RD001/RD002) are candidates, NOT confirmed errors — "
    "   mention they need human review when relevant. "
    "5) Answer in the same language as the user's question. If the question "
    "   is Arabic, use clear Modern Standard Arabic while preserving rule IDs "
    "   and feature IDs exactly. If it is English, answer in English. "
    "6) The context contains a 'remediation' audit of what the agent did about "
    "   each error: action=auto_fix with status=applied means it was repaired "
    "   automatically (only invalid-geometry fixes BLD003/RD004 are ever "
    "   automatic); action=human_review with status=pending_review means it is "
    "   queued for a human reviewer; action=auto_fix with status=failed means "
    "   the automatic repair was attempted, rolled back and logged; "
    "   action=no_action with status=none means nothing was done (layer-level "
    "   guidance only). When the user asks what was fixed automatically or "
    "   what still needs a human, answer from the remediation summary/items — "
    "   do NOT claim something was auto-fixed unless the audit says applied, "
    "   and do NOT claim something needs a human if it was already applied."
)

MAX_CHAT_ANALYSES = 100


def _question_language(question: str) -> str:
    """Choose the response language from the user's actual question."""
    return "Arabic" if any("\u0600" <= char <= "\u06ff" for char in question) else "English"


def build_chat_context(repo: Repository, run_id: str) -> dict:
    """Assemble the grounded context for one run."""
    analyses = repo.fetch_analyses(run_id)
    if not analyses:
        raise ValueError(
            f"No agent analysis found for run {run_id}. "
            "Run POST /api/validation/{run_id}/analyze (or the CLI analyze) first.")
    results = repo.fetch_results(run_id)
    summary = repo.build_summary(results, analyses)
    summary["priority_actions"] = repo.priority_actions(summary)
    rules: dict[str, dict] = {}
    for a in analyses:
        rd = get_rule(a.rule_id)
        if rd is not None:
            rules[a.rule_id] = {"type": rd.type,
                                "requires_human_review": rd.requires_human_review,
                                "recommendation": rd.recommendation}
    return {
        "run_id": run_id,
        "summary": summary,
        "analyses": [
            a.model_dump()
            for a in analyses[:MAX_CHAT_ANALYSES]
        ],
        "analyses_in_context": min(
            len(analyses),
            MAX_CHAT_ANALYSES,
        ),
        "total_analyses": len(analyses),
        "rules": rules,
        "remediation": _remediation_context(repo, run_id),
    }


def _remediation_context(repo: Repository, run_id: str) -> dict:
    """Compact remediation audit for the chat prompt.

    Kept small on purpose: counts + one short item per record so the model
    can truthfully say what was auto-fixed / queued / failed without burning
    tokens on full before/after GeoJSON.
    """
    try:
        records = repo.fetch_remediation_records(run_id) or []
    except Exception:
        # The audit table may not exist on older DBs — chat must not break.
        return {"available": False, "summary": {}, "items": []}
    applied = sum(1 for r in records
                  if r.get("action") == "auto_fix" and r.get("status") == "applied")
    failed = sum(1 for r in records if r.get("status") == "failed")
    pending = sum(1 for r in records
                  if r.get("action") == "human_review"
                  and r.get("status") == "pending_review")
    no_action = sum(1 for r in records
                    if r.get("action") == "no_action")
    summary = {
        "total": len(records),
        "auto_fixed": applied,
        "failed": failed,
        "pending_review": pending,
        "no_action": no_action,
    }
    items = []
    for r in records[:MAX_CHAT_ANALYSES]:
        reason = str(r.get("reason") or "")[:180]
        items.append({
            "rule_id": r.get("rule_id"),
            "feature_id": r.get("feature_id"),
            "action": r.get("action"),
            "status": r.get("status"),
            "remediation_type": r.get("remediation_type"),
            "issue": str(r.get("issue") or "")[:140],
            "reason": reason,
            "human_review_required": bool(r.get("human_review_required")),
        })
    return {"available": True, "summary": summary, "items": items}


def _code_fence_strip(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1]
        t = t.rsplit("\n", 1)[0] if t.endswith("```") else t
        if t.endswith("```"):
            t = t[:-3].strip()
    return t.strip()


def answer_question(repo: Repository, run_id: str, question: str,
                    llm: Optional[Any] = None) -> dict:
    """Answer a question about a run. Returns {question, answer, sources}."""
    llm = llm or get_llm()
    if llm is None:
        raise RuntimeError(
            "Chat requires an LLM key (MEYAAR_LLM_API_KEY in agent/.env). "
            "The analysis endpoints work without one; chat does not.")

    context = build_chat_context(repo, run_id)
    payload = json.dumps(context, ensure_ascii=False, default=str)
    response_language = _question_language(question)
    prompt = (
        "System instructions:\n" + SYSTEM_PROMPT +
        "\n\nRequired response language: " + response_language + ". "
        "The answer field MUST be written in that language. "
        "Keep technical IDs unchanged internally, but omit them from the visible "
        "answer unless the user explicitly requests them. Summarize repeated "
        "findings by category instead of listing long identifiers.\n\nContext (JSON): " + payload +
        "\n\nUser question: " + question +
        "\n\nReply STRICT JSON only: "
        '{"answer": "your answer", "sources": ["RULE@feature", "..."]} '
        "where each source is a finding present in the context (rule_id@feature_id)."
    )
    attempts = max(1, settings.llm_retries)
    answer = ""
    sources_raw: list = []
    for _ in range(attempts):
        try:
            resp = llm.invoke(prompt)
            parsed = json.loads(_code_fence_strip(str(resp.content)))
            answer = str(parsed.get("answer", "")).strip()
            if answer:
                sources_raw = parsed.get("sources") or []
                break
        except Exception:
            continue
    if not answer:
        raise RuntimeError("The model did not return a valid answer; try again.")

    # Filter sources to ids that genuinely exist in the context.
    known = set()
    for a in context["analyses"]:
        known.add(f"{a['rule_id']}@{a.get('feature_id') or ''}".rstrip("@"))
        known.add(a["rule_id"])
        if a.get("feature_id"):
            known.add(a["feature_id"])
    sources = []
    for s in sources_raw:
        s = str(s).strip()
        if s in known and s not in sources:
            sources.append(s)
    return {"question": question, "answer": answer, "sources": sources}
