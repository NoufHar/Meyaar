"""AgentState for the Error Analysis workflow.

Kept as plain dataclasses + pydantic models; JSON-friendly throughout.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from agent.core.models import ErrorAnalysis, ValidationResult


@dataclass
class PreparedGroup:
    """A (layer, rule) batch prepared with context for one LLM call."""

    layer_name: str
    rule_id: str
    rule: Optional[dict] = None
    items: list = field(default_factory=list)   # per-result payloads
    contexts: dict = field(default_factory=dict)  # feature_id -> context


@dataclass
class AgentState:
    run_id: str = ""
    results: list[ValidationResult] = field(default_factory=list)
    groups: list[PreparedGroup] = field(default_factory=list)
    analyses: list[ErrorAnalysis] = field(default_factory=list)
    summary: Optional[dict] = None
    trace: list = field(default_factory=list)
    errors: list = field(default_factory=list)   # logged, never fatal to run

    def to_result_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "results_loaded": len(self.results),
            "analyses": [a.model_dump() for a in self.analyses],
            "summary": self.summary,
            "trace": self.trace,
            "errors": self.errors,
        }
