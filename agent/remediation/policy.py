"""Remediation policy helpers — read the rule registry fields added in Part 4.

The registry (rules/registry.json) is the single source of truth for:

    remediation_type         what kind of fix applies (geometry_repair,
                             attribute_correction, crs_transform, human_review)
    auto_fix_allowed         may the agent execute the fix automatically?
    remediation_description  human-readable policy rationale

IMPORTANT: `auto_fix_allowed: true` only *permits* automatic execution; the
service additionally requires the remediation_type to be one of the ops that
is actually implemented (IMPLEMENTED_OPS). Anything else degrades safely to
human review — an LLM can never widen this set.
"""
from __future__ import annotations

from typing import Optional

# Remediation operations with an implemented, whitelisted, transactional
# repository method. If a registry entry declares auto_fix_allowed for a type
# NOT in this set, the service refuses to auto-execute (falls back to review).
IMPLEMENTED_OPS = frozenset({"geometry_repair"})


def auto_fix_allowed(rule: Optional[dict]) -> bool:
    """True only when the registry permits auto-fix AND the op is implemented."""
    if not rule:
        return False
    if not bool(rule.get("auto_fix_allowed")):
        return False
    return rule.get("remediation_type") in IMPLEMENTED_OPS


def remediation_type(rule: Optional[dict]) -> Optional[str]:
    return rule.get("remediation_type") if rule else None


def remediation_description(rule: Optional[dict]) -> str:
    return (rule or {}).get("remediation_description", "") or ""
