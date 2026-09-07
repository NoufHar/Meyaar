"""Pydantic schemas for the Error Analysis Agent.

These models are the contract between the graph, the tools, the database
and the API. All outputs stay JSON-serializable.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

SEVERITIES = ("critical", "high", "medium", "low")
STATUSES = ("confirmed", "candidate", "informational", "insufficient_context")
RULE_TYPES = ("deterministic", "heuristic")

REMEDIATION_ACTIONS = ("auto_fix", "human_review", "no_action")
REMEDIATION_STATUSES = ("applied", "failed", "pending_review", "none")
# remediation_type values the registry may declare (only implemented ops may
# ever be auto-executed; everything else resolves to human review).
REMEDIATION_TYPES = ("geometry_repair", "human_review",
                     "attribute_correction", "crs_transform")


class ValidationResult(BaseModel):
    """One row of public.validation_results (source of truth)."""

    result_id: int
    run_id: str
    layer_name: str
    feature_id: Optional[str] = None
    rule_id: str
    error_type: str
    severity: str
    details: Optional[str] = None
    detected_at: Optional[str] = None


class RuleDefinition(BaseModel):
    """Maintainable rule-definition record (rules/registry.json)."""

    rule_id: str
    error_type: str                 # matches validation_results.error_type
    name: str
    description: str
    baseline_severity: str
    type: str = Field(..., pattern="^(deterministic|heuristic)$")
    requires_human_review: bool = False
    layer: str = ""                 # buildings | roads | general
    recommendation: str = ""        # resolution guidance used by the template path
    priority_hint: str = ""         # e.g. "resolve before editing adjacent features"

    # ── remediation policy (Part 4 of the extension) ─────────────────────
    # The registry is the policy source of truth. The LLM can suggest a
    # remediation action, but it can never override these values: the
    # deterministic layer (agent/remediation/service.py) reads them to decide
    # auto_fix vs human_review vs no_action.
    remediation_type: str = "human_review"
    auto_fix_allowed: bool = False
    remediation_description: str = ""


class ErrorAnalysis(BaseModel):
    """Agent interpretation of ONE validation result (agent_error_analysis)."""

    result_id: int
    run_id: str
    layer_name: str
    feature_id: Optional[str] = None
    rule_id: str
    error_type: str
    severity: str
    status: str = Field(..., pattern="^(confirmed|candidate|informational|insufficient_context)$")
    explanation: str
    cause: Optional[str] = None
    recommendation: Optional[str] = None
    human_review_required: bool = False
    related_features: list[str] = Field(default_factory=list)
    insufficient_context: bool = False
    agent_model: str = ""


class RunSummary(BaseModel):
    """Run-level rollup returned alongside individual analyses."""

    run_id: str
    total_errors: int = 0
    critical_errors: int = 0
    high_errors: int = 0
    medium_errors: int = 0
    low_errors: int = 0
    most_common_error: Optional[str] = None
    priority_actions: list[str] = Field(default_factory=list)
    counts_by_rule: dict[str, int] = Field(default_factory=dict)
    counts_by_layer: dict[str, int] = Field(default_factory=dict)
    # Executive narrative written at the end of the workflow and persisted to
    # agent_run_summaries (LLM-generated or deterministic template).
    narrative: Optional[str] = None


class AnalyzeResponse(BaseModel):
    """POST /api/validation/{run_id}/analyze body."""

    run_id: str
    status: str
    total_errors_analyzed: int = 0
    message: str = ""


class AnalysisListResponse(BaseModel):
    """GET /api/validation/{run_id}/analysis body."""

    run_id: str
    summary: RunSummary
    analyses: list[ErrorAnalysis] = Field(default_factory=list)


# ── remediation (Part 5 / 7 / 9 of the extension) ──────────────────────────

class RemediationDecision(BaseModel):
    """Structured remediation decision for ONE validation result.

    Produced by the deterministic policy layer (agent/remediation/service.py).
    The LLM never decides directly: it may *suggest* an action, but the
    decision is validated against the rule registry and only then executed.
    """

    result_id: int
    action: str = Field(..., pattern="^(auto_fix|human_review|no_action)$")
    remediation_type: Optional[str] = None
    reason: str = ""
    confidence: Optional[float] = None
    proposed_changes: dict = Field(default_factory=dict)
    human_review_required: bool = False


class RemediationRecord(BaseModel):
    """Audit row for public.agent_remediation_actions.

    One record per (run_id, result_id). Kept JSON-friendly; before/after
    states are dicts (JSONB in PostgreSQL). The dashboard can distinguish:
    action=auto_fix + status=applied  -> automatically fixed
    action=human_review + status=pending_review -> requires human reviewer
    action=no_action + status=none    -> nothing to do
    action=auto_fix + status=failed   -> execution failed (logged)
    """

    remediation_id: Optional[int] = None
    run_id: str
    result_id: int
    layer_name: str
    feature_id: Optional[str] = None
    rule_id: str
    action: str = Field(..., pattern="^(auto_fix|human_review|no_action)$")
    remediation_type: Optional[str] = None
    status: str = Field(..., pattern="^(applied|failed|pending_review|none)$")
    issue: str = ""                 # what the engine flagged (error_type + detail)
    reason: str = ""                # why auto-fix was (not) performed
    recommended_action: Optional[str] = None
    before_state: dict = Field(default_factory=dict)
    after_state: dict = Field(default_factory=dict)
    agent_model: str = ""
    human_review_required: bool = False
    executed_at: Optional[str] = None


class RemediationListResponse(BaseModel):
    """GET /api/validation/{run_id}/remediation body."""

    run_id: str
    remediation: list[RemediationRecord] = Field(default_factory=list)
