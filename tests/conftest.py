"""Shared fixtures for the test suite.

Provides helpers for exercising the transcribe→align path with a sample WAV:
  - `wav_factory`        writes a valid 16 kHz mono WAV (Whisper is mocked, so the
                         audio content is irrelevant — the file just needs to exist).
  - `make_whisper_output` builds a faithful transformers word-timestamp dict.
  - `patched_asr`        patches WhisperASRService._get_pipeline to return a fake pipe.
  - `say_wav_factory`    synthesizes real spoken audio via macOS `say` + ffmpeg
                         (used only by the opt-in real-model test).
  - `engine`             a fresh AlignmentEngine.
"""
import shutil
import subprocess
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import soundfile as sf

from src.alignment import AlignmentEngine
from src.pipeline import WhisperASRService

SAMPLE_RATE = 16000


@pytest.fixture
def engine():
    return AlignmentEngine()


@pytest.fixture
def wav_factory(tmp_path):
    """Return a factory that writes a valid mono WAV and returns its path."""
    def _make(duration_s: float = 1.0, name: str = "sample.wav") -> str:
        t = np.linspace(0, duration_s, int(SAMPLE_RATE * duration_s), endpoint=False)
        # A quiet sine — content doesn't matter (Whisper is mocked), but a real
        # waveform keeps the file representative of an actual recording.
        audio = 0.01 * np.sin(2 * np.pi * 220 * t).astype(np.float32)
        path = tmp_path / name
        sf.write(path, audio, SAMPLE_RATE)
        return str(path)
    return _make


@pytest.fixture
def make_whisper_output():
    """Build a transformers ASR dict (return_timestamps='word' shape).

    Mirrors exactly what WhisperASRService._parse_whisper_output expects:
    {"text": <full>, "chunks": [{"text": " word", "timestamp": (start, end),
    "probability": p}, ...]} with monotonic timestamps.
    """
    def _make(transcript: str, word_dur: float = 0.3, gap: float = 0.1) -> dict:
        words = transcript.split()
        chunks = []
        cursor = 0.0
        for w in words:
            start = cursor
            end = start + word_dur
            chunks.append({"text": f" {w}", "timestamp": (start, end), "probability": 0.95})
            cursor = end + gap
        return {"text": transcript, "chunks": chunks}
    return _make


@pytest.fixture
def patched_asr(make_whisper_output):
    """Context manager: patch _get_pipeline so transcribe_file returns canned output.

    Usage:
        with patched_asr("the cat sat") as service:
            result = service.transcribe_file(wav_path)
    """
    @contextmanager
    def _patched(transcript: str, model_name: str = "openai/whisper-medium"):
        canned = make_whisper_output(transcript)
        fake_pipe = MagicMock(return_value=canned)
        with patch.object(WhisperASRService, "_get_pipeline", return_value=fake_pipe):
            yield WhisperASRService(model_name=model_name)
    return _patched


@pytest.fixture
def say_wav_factory(tmp_path):
    """Synthesize real spoken audio via macOS `say` + ffmpeg → 16 kHz mono WAV.

    Skips the calling test if `say` or `ffmpeg` is unavailable.
    """
    def _make(text: str, voice: str | None = None, name: str = "spoken.wav") -> str:
        if shutil.which("say") is None or shutil.which("ffmpeg") is None:
            pytest.skip("requires macOS `say` and `ffmpeg` to synthesize speech")
        aiff = tmp_path / "spoken.aiff"
        wav = tmp_path / name
        say_cmd = ["say", "-o", str(aiff)]
        if voice:
            say_cmd += ["-v", voice]
        say_cmd.append(text)
        subprocess.run(say_cmd, check=True)
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(aiff), "-ar", str(SAMPLE_RATE), "-ac", "1", str(wav)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        aiff.unlink(missing_ok=True)
        return str(wav)
    return _make
