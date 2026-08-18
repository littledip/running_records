import platform
import shutil
import sys
from unittest.mock import MagicMock

import pytest

from src.tts import synthesize_speech


def test_synthesize_speech_returns_wav_bytes():
    if shutil.which("say") is None or shutil.which("ffmpeg") is None:
        pytest.skip("requires macOS `say` and `ffmpeg`")

    audio = synthesize_speech("Hello there.")

    assert isinstance(audio, bytes)
    assert len(audio) > 0
    assert audio[:4] == b"RIFF"


def test_synthesize_speech_raises_without_tools(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _name: None)

    with pytest.raises(RuntimeError):
        synthesize_speech("Hello there.")


def test_synthesize_speech_raises_on_unsupported_platform(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Linux")

    with pytest.raises(RuntimeError, match="not supported"):
        synthesize_speech("Hello there.")


def test_synthesize_speech_windows_dispatches_sapi(monkeypatch):
    """Drives the Windows (SAPI5) branch with a mocked win32com.client, since
    pywin32 isn't installed/importable on this (non-Windows) test host."""
    monkeypatch.setattr(platform, "system", lambda: "Windows")

    fake_stream = MagicMock()
    fake_speaker = MagicMock()
    fake_audio_format = MagicMock()
    fake_win32com_client = MagicMock()
    fake_win32com_client.Dispatch.side_effect = lambda prog_id: {
        "SAPI.SpVoice": fake_speaker,
        "SAPI.SpFileStream": fake_stream,
        "SAPI.SpAudioFormat": fake_audio_format,
    }[prog_id]
    fake_win32com = MagicMock(client=fake_win32com_client)
    monkeypatch.setitem(sys.modules, "win32com", fake_win32com)
    monkeypatch.setitem(sys.modules, "win32com.client", fake_win32com_client)

    audio = synthesize_speech("Hello there.")

    assert isinstance(audio, bytes)
    assert fake_audio_format.Type == 18  # SAFT16kHz16BitMono
    fake_stream.Open.assert_called_once()
    assert fake_stream.Open.call_args[0][1] == 3  # SSFMCreateForWrite
    fake_speaker.Speak.assert_called_once_with("Hello there.")
    fake_stream.Close.assert_called_once()
