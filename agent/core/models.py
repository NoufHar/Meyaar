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
