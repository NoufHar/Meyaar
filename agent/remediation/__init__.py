"""Deterministic remediation layer for the Error Analysis Agent.

Trust boundary (trainer requirement): the LLM interprets and *proposes*;
deterministic application code verifies and executes. This package holds the
policy decision service and the audit record model:

    agent/remediation/service.py   decide() + execute helpers
    agent/remediation/policy.py    rule-registry policy accessors

The rule registry (rules/registry.json) remains the policy source of truth;
nothing here lets the LLM override it.
"""
