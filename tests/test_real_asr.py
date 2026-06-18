"""Opt-in end-to-end test against the real whisper-medium model.

Auto-skipped unless BOTH are present:
  - HUGGING_FACE_HUB_TOKEN (the pipeline requires it), and
  - RUN_REAL_ASR=1 (explicit opt-in, since this downloads the model and is slow).

Run with:
    RUN_REAL_ASR=1 pytest -m integration -v
"""
import os

import pytest

from src.alignment import AlignmentEngine
from src.pipeline import WhisperASRService

pytestmark = pytest.mark.integration

SHOULD_RUN = os.getenv("RUN_REAL_ASR") == "1" and bool(os.getenv("HUGGING_FACE_HUB_TOKEN"))

skip_reason = "set RUN_REAL_ASR=1 and HUGGING_FACE_HUB_TOKEN to run the real-model test"

TARGET = "The rain in Spain stays mainly in the plain."


@pytest.mark.skipif(not SHOULD_RUN, reason=skip_reason)
def test_real_transcribe_align_perfect_read(say_wav_factory):
    """Synthesized speech of the target should transcribe and align with high accuracy."""
    wav = say_wav_factory(TARGET)

    asr = WhisperASRService()
    result = asr.transcribe_file(wav)
    result.target_text = TARGET
    alignment = AlignmentEngine().process_result(result)

    # Tolerant: TTS + ASR aren't bit-exact, but content words should land.
    assert alignment.metrics.accuracy >= 0.8, (
        f"accuracy={alignment.metrics.accuracy:.2f}, "
        f"transcript={alignment.transcript_text!r}"
    )
    transcript = alignment.transcript_text.lower()
    for key_word in ("rain", "spain", "plain"):
        assert key_word in transcript, f"missing {key_word!r} in {transcript!r}"
