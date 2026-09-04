"""Voice-layer tests (no audio hardware needed)."""
from __future__ import annotations

import pytest

from agent import voice
from agent.voice import available_engines, speech_to_text, text_to_speech


def test_tts_none_engine_raises():
    with pytest.raises(RuntimeError, match="TTS disabled"):
        text_to_speech("hello", engine="none")


def test_tts_unknown_engine_raises():
    with pytest.raises(RuntimeError, match="Unsupported TTS engine"):
        text_to_speech("hello", engine="alien")


def test_tts_macos_without_say_raises(monkeypatch):
    monkeypatch.setattr(voice.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="'say' command"):
        text_to_speech("hello", engine="macos")


def test_tts_macos_invokes_say(monkeypatch):
    import subprocess
    calls = []

    class FakePopen:
        def __init__(self, *a, **k):
            calls.append((a, k))

    monkeypatch.setattr(voice.shutil, "which", lambda name: "/usr/bin/say")
    monkeypatch.setattr(voice.subprocess, "Popen", FakePopen)
    assert text_to_speech("hello", engine="macos") is True
    cmd = calls[0][0][0]      # positional args of the Popen call
    assert cmd and cmd[0].endswith("say") and "hello" in cmd


def test_stt_not_implemented_server_side():
    with pytest.raises(NotImplementedError, match="not implemented"):
        speech_to_text("whatever.wav", engine="none")


def test_available_engines_shape():
    info = available_engines()
    assert set(info) >= {"tts", "tts_ready", "stt", "stt_ready", "ui_stt", "ui_tts"}
    assert info["ui_stt"].startswith("browser")
    assert info["ui_tts"].startswith("browser")
