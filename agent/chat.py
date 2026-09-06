"""Grounded chat over a run's validation results and agent analyses.

The chat answers questions about ONE engine run using ONLY:
  - the run summary (counts, most common error, priority actions)
  - the stored agent analyses (explanations, causes, recommendations)
  - the rule registry (rule meaning, heuristic vs deterministic)

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
    "(run summary + per-error analyses). Rules: "
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
    "   and feature IDs exactly. If it is English, answer in English."
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
    }


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
