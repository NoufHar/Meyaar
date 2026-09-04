"""Voice integration for the Meyaar agent (thin, provider-optional).

Design principle from the role: integrate, do not build a heavy voice stack.
Pipeline:  Speech -> STT -> Agent (chat) -> Response -> TTS

Implemented now:
  * TTS "macos" engine  -> the system `say` command (works on macOS, zero deps)
  * TTS "none"          -> explicit no-op (raise) for CI/headless tests
  * STT engine "none"   -> the chat UI uses the BROWSER Web Speech API for
                           speech-to-text; server-side STT can be added later
                           (e.g. MEYAAR_STT_ENGINE=openai-whisper) without
                           changing the interface below.

Config:  MEYAAR_TTS_ENGINE = macos | none
         MEYAAR_STT_ENGINE = none   (reserved: openai-whisper, local-whisper)
"""
from __future__ import annotations

import logging
import shutil
import subprocess

from agent.core.config import settings

logger = logging.getLogger(__name__)


def text_to_speech(text: str, engine: str | None = None) -> bool:
    """Speak `text` aloud. Returns True if the engine accepted the request.

    Raises RuntimeError when no usable engine is configured (callers should
    treat this as non-fatal and continue with the text answer).
    """
    engine = (engine or settings.tts_engine).lower()
    if engine == "macos":
        say = shutil.which("say")
        if say is None:
            raise RuntimeError("TTS engine 'macos' requested but the 'say' "
                               "command was not found on this system.")
        try:
            # Non-blocking: say schedules speech and returns immediately.
            subprocess.Popen([say, "-r", "185", "--", text[:4000]],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            return True
        except Exception as exc:
            logger.warning("macos say failed: %s", exc)
            raise RuntimeError(f"macos say failed: {exc}") from exc
    if engine == "none":
        raise RuntimeError("TTS disabled (MEYAAR_TTS_ENGINE=none).")
    raise RuntimeError(f"Unsupported TTS engine: {engine!r} "
                       "(supported: macos, none)")


def speech_to_text(audio_path: str, engine: str | None = None) -> str:
    """Transcribe audio to text. Not implemented server-side yet.

    The chat UI performs STT in the browser (Web Speech API). A server-side
    engine can be added here without touching callers.
    """
    engine = (engine or settings.stt_engine).lower()
    raise NotImplementedError(
        f"Server-side STT engine '{engine}' is not implemented. "
        "Use the chat UI microphone (browser Web Speech API) for now, or set "
        "MEYAAR_STT_ENGINE to a supported engine when one is added.")


def available_engines() -> dict:
    """Report what the voice layer can do (used by /api/info and the UI)."""
    return {
        "tts": settings.tts_engine,
        "tts_ready": settings.tts_engine == "macos" and shutil.which("say") is not None,
        "stt": settings.stt_engine,
        "stt_ready": False,
        "ui_stt": "browser (Web Speech API)",
        "ui_tts": "browser (speechSynthesis)",
    }
