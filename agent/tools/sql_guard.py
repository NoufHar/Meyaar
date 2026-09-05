"""Read-only SQL guard for query_postgis (defense in depth).

The Postgres engine ALSO opens connections with default_transaction_read_only=on
so PostgreSQL itself rejects writes even if this guard is ever bypassed.
"""
from __future__ import annotations

import re

FORBIDDEN_KEYWORDS = (
    "insert", "update", "delete", "drop", "alter", "truncate", "create",
    "grant", "revoke", "merge", "replace", "copy", "vacuum", "analyze",
    "lock", "call", "comment", "reindex", "refresh", "security",
    "listen", "notify", "unlisten", "cluster", "reassign", "import",
)

# Strip string literals and comments so keywords inside them cannot spoof
# the guard (e.g. a data value containing the word 'drop').
_STRING_PATTERN = (
    r"'(?:[^']|'')*'"          # single-quoted literal
    r'|"(?:[^"]|"")*"'         # double-quoted identifier
    r"|--[^\n]*"               # line comment
    r"|/\*.*?\*/"              # block comment
    r"|\$[a-z_]*\$.*?\$[a-z_]*\$"  # dollar-quoted body (plpgsql)
)
_STRIP_RE = re.compile(_STRING_PATTERN, re.IGNORECASE | re.DOTALL)


def _strip_literals(sql: str) -> str:
    return _STRIP_RE.sub(" ", sql)


def assert_readonly_sql(sql: str) -> None:
    """Raise ValueError unless `sql` is a single read-only statement."""
    if not isinstance(sql, str) or not sql.strip():
        raise ValueError("query_postgis: empty SQL is not allowed")

    stripped = sql.strip().rstrip(";").strip()
    if ";" in stripped:
        raise ValueError("query_postgis: multiple statements are not allowed")

    lowered = _strip_literals(stripped).lower()
    if not (lowered.startswith("select")
            or lowered.startswith("with")
            or lowered.startswith("explain")):
        raise ValueError("query_postgis: only SELECT (read-only) queries are allowed")

    words = set(re.findall(r"[a-z_]+", lowered))
    if "into" in words:
        raise ValueError("query_postgis: SELECT ... INTO is not allowed")
    for kw in FORBIDDEN_KEYWORDS:
        if kw in words:
            raise ValueError(f"query_postgis: forbidden keyword '{kw}'")
