"""Shared LLM factory with caching.

`get_llm()` returns None when no API key is configured — callers MUST handle
None by falling back to deterministic template generation (no API calls in
tests/CI). Supports any OpenAI-compatible endpoint via base_url.
"""
from __future__ import annotations

from typing import Optional

from agent.core.config import settings

_llm_cache: dict[tuple, object] = {}


def get_llm() -> Optional[object]:
    """Return a cached ChatOpenAI instance or None (LLM disabled)."""
    if not settings.llm_enabled:
        return None
    key = (settings.llm_base_url, settings.llm_model,
           settings.llm_temperature, settings.llm_max_tokens)
    if key not in _llm_cache:
        from langchain_openai import ChatOpenAI

        kwargs: dict = {
            "model": settings.llm_model,
            "temperature": settings.llm_temperature,
            "max_tokens": settings.llm_max_tokens,
            "api_key": settings.llm_api_key,
        }
        if settings.llm_base_url:
            kwargs["base_url"] = settings.llm_base_url
        _llm_cache[key] = ChatOpenAI(**kwargs)
    return _llm_cache[key]
