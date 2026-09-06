"""Deterministic remediation decision service (Part 2 / 3 / 10).

Flow enforced here:

    LLM analysis (explanation / recommendation / optional intent)
            |
            v
    decide()  ->  deterministic policy from the rule registry
            |
            v
    auto_fix        human_review        no_action
    (only when the registry allows it AND the op is implemented)
            |
            v
    node executes via repo.apply_geometry_repair()  (transactional, audited)

The LLM can never change: rule_id, severity, feature_id, layer_name, whether
a rule is heuristic, whether human review is required, whether auto-fix is
allowed, or the exact SQL operation executed. If the LLM suggests something
the policy forbids (e.g. auto-fixing a heuristic candidate), the suggestion
is ignored and the reason field records the override.
"""
from __future__ import annotations

from typing import Optional

from agent.core.models import (
    RemediationDecision,
    ValidationResult,
)
from agent.remediation import policy as remediation_policy

VALID_ACTIONS = ("auto_fix", "human_review", "no_action")
_LLM_FORBIDDEN_OVERRIDE = (
    "LLM cannot override the remediation policy in rules/registry.json"
)


def _intent_action(llm_intent: Optional[dict]) -> Optional[str]:
    """Normalized LLM-suggested action, or None when absent/invalid."""
    if not isinstance(llm_intent, dict):
        return None
    raw = llm_intent.get("action")
    if not isinstance(raw, str):
        return None
    action = raw.strip().lower()
    return action if action in VALID_ACTIONS else None


def _policy_intent_note(llm_intent: Optional[dict]) -> str:
    """Why an LLM suggestion was ignored ("" when nothing to report)."""
    if not isinstance(llm_intent, dict) or not llm_intent.get("action"):
        return ""
    raw = str(llm_intent.get("action")).strip()
    action = _intent_action(llm_intent)
    if action is None:
        return (f"LLM suggested invalid remediation action {raw!r} — ignored. "
                f"{_LLM_FORBIDDEN_OVERRIDE}.")
    return (f"LLM suggested {action!r} but the registry policy governs — "
            f"{_LLM_FORBIDDEN_OVERRIDE}. ")


def decide(result: ValidationResult,
           analysis,
           rule: Optional[dict],
           llm_intent: Optional[dict] = None,
           feature_available: bool = True) -> RemediationDecision:
    """Deterministic remediation decision for ONE analyzed result.

    Args:
        result:       the engine row (source of truth).
        analysis:     the ErrorAnalysis for this result.
        rule:         registry rule dict (rules/registry.json), or None for
                      an unregistered/unknown rule id.
        llm_intent:   OPTIONAL advisory dict {"action": ..., "reason": ...}
                      from the LLM. Never overrides the policy below.
        feature_available: whether the feature row exists in the layer DB
                      (checked by the caller). Auto-fix is refused when the
                      target feature cannot be located.

    Returns a validated RemediationDecision; nothing is executed here.
    """
    note = _policy_intent_note(llm_intent)

    # 1. No registry policy -> nothing safe to do.
    if rule is None:
        return RemediationDecision(
            result_id=result.result_id, action="no_action",
            remediation_type=None,
            reason=note + "Rule is not registered in rules/registry.json — "
                          "no remediation policy; nothing safe to do.",
            human_review_required=False)

    # 2. Informational (unknown/registry-less detections) -> no action.
    if analysis.status == "informational":
        return RemediationDecision(
            result_id=result.result_id, action="no_action",
            remediation_type=rule.get("remediation_type"),
            reason=note + "Informational detection — no remediation required.",
            human_review_required=False)

    # 3. Missing source information -> human review, never invention.
    if analysis.status == "insufficient_context":
        return RemediationDecision(
            result_id=result.result_id, action="human_review",
            remediation_type=rule.get("remediation_type"),
            reason=note + "No rule-engine details and/or feature context are "
                          "available, so the correct fix cannot be determined "
                          "or proven safe — escalate to a human reviewer.",
            human_review_required=True)

    # 4. Heuristic rules (RD001/RD002) -> human review, always.
    if rule.get("type") == "heuristic" or analysis.human_review_required:
        return RemediationDecision(
            result_id=result.result_id, action="human_review",
            remediation_type=rule.get("remediation_type"),
            reason=note + "Heuristic detection (or registry human-review flag): "
                          "automatic correction is not safe — escalate to a "
                          "human reviewer.",
            human_review_required=True)

    # 5. Registry allows auto-fix AND the op is implemented AND the target
    #    feature exists AND the analysis is confirmed -> approved auto-fix.
    if (remediation_policy.auto_fix_allowed(rule)
            and analysis.status == "confirmed"
            and analysis.feature_id
            and feature_available):
        op = rule.get("remediation_type")
        return RemediationDecision(
            result_id=result.result_id, action="auto_fix",
            remediation_type=op,
            reason=note + "Registry policy approves automatic execution "
                          f"({op}); target feature present; analysis confirmed.",
            confidence=1.0,
            proposed_changes={
                "operation": op,
                "target_layer": analysis.layer_name,
                "target_feature_id": analysis.feature_id,
            },
            human_review_required=False)

    # 6. Registry would allow auto-fix, but we cannot locate the feature.
    if (remediation_policy.auto_fix_allowed(rule)
            and analysis.status == "confirmed"):
        return RemediationDecision(
            result_id=result.result_id, action="human_review",
            remediation_type=rule.get("remediation_type"),
            reason=note + "Auto-fix is policy-approved but the target feature "
                          "row could not be located — do not mutate blindly; "
                          "escalate to a human reviewer.",
            human_review_required=True)

    # 7. Layer-level issue (no single feature to fix) -> no action, but keep
    #    the registry guidance so the human/data owner sees the recommendation.
    if not analysis.feature_id:
        return RemediationDecision(
            result_id=result.result_id, action="no_action",
            remediation_type=rule.get("remediation_type"),
            reason=note + "Layer-level issue with no specific feature to "
                          "mutate — outside the agent's per-feature "
                          "remediation scope (see recommended action).",
            human_review_required=False)

    # 8. Everything else deterministic-but-not-auto-fixable -> human review.
    return RemediationDecision(
        result_id=result.result_id, action="human_review",
        remediation_type=rule.get("remediation_type"),
        reason=note + "Registry policy does not allow automatic correction for "
                      "this error type — escalate to a human reviewer.",
        human_review_required=True)
