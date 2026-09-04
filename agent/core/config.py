"""Environment-driven settings for the Meyaar Error Analysis Agent.

DB defaults mirror the team's PostGIS setup (src/insertion/database.py):
postgres@localhost:5432/meyaar_db. Override with MEYAAR_DATABASE_URL.
"""
from __future__ import annotations

import os
from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parent.parent  # .../agent

DEFAULT_DATABASE_URL = "postgresql+psycopg2://postgres@localhost:5432/meyaar_db"


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    def __init__(self) -> None:
        # Database
        self.database_url: str = os.getenv("MEYAAR_DATABASE_URL", DEFAULT_DATABASE_URL).strip()
        # Read-only enforcement: every connection from the analysis layer gets
        # default_transaction_read_only=on so even a buggy query cannot write.
        self.db_read_only_options: str = os.getenv(
            "MEYAAR_DB_READ_ONLY_OPTIONS", "-c default_transaction_read_only=on")

        # LLM (any OpenAI-compatible provider; optional)
        self.llm_api_key: str = (os.getenv("MEYAAR_LLM_API_KEY", "").strip()
                                 or os.getenv("OPENAI_API_KEY", "").strip())
        self.llm_base_url: str = os.getenv("MEYAAR_LLM_BASE_URL", "").strip()
        self.llm_model: str = os.getenv("MEYAAR_LLM_MODEL", "gpt-4o-mini").strip()
        try:
            self.llm_temperature: float = float(os.getenv("MEYAAR_LLM_TEMPERATURE", "0.0"))
        except ValueError:
            self.llm_temperature = 0.0
        try:
            self.llm_max_tokens: int = int(os.getenv("MEYAAR_LLM_MAX_TOKENS", "2048"))
        except ValueError:
            self.llm_max_tokens = 2048
        self.llm_retries: int = int(os.getenv("MEYAAR_LLM_RETRIES", "2"))
        self.allow_llm: bool = _env_bool("MEYAAR_ALLOW_LLM", True)

        # Voice (thin integration; engines are provider-optional)
        #   tts: macos ("say") | none   (future: openai | edge)
        #   stt: none (UI uses the browser Web Speech API) | future: whisper…
        self.tts_engine: str = os.getenv("MEYAAR_TTS_ENGINE", "macos").strip().lower()
        self.stt_engine: str = os.getenv("MEYAAR_STT_ENGINE", "none").strip().lower()

    @property
    def llm_enabled(self) -> bool:
        """True only when an API key is configured AND LLM use is allowed."""
        return self.allow_llm and bool(self.llm_api_key)

    @property
    def agent_model(self) -> str:
        return self.llm_model if self.llm_enabled else "template-fallback"


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(_PACKAGE_DIR / ".env")
    except Exception:
        pass


_load_dotenv()
# Re-read after .env load: simplest is to instantiate after load_dotenv ran.
settings = Settings()
