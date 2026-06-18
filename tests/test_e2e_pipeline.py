"""Fast, deterministic end-to-end tests for the transcribe→align path.

Feeds a real WAV through the *real* WhisperASRService.transcribe_file ->
_parse_whisper_output glue (Whisper mocked at the _get_pipeline boundary), then
through the *real* AlignmentEngine. This covers the exact 3-step flow the app runs
in pages/student_record.py::run_assessment_pipeline, without needing the model,
an HF token, or network access.
"""
import pytest

from src.models import AlignmentResult
from src.pipeline import WhisperASRService


def _run(service, wav_path, target_text):
    """Mirror pages/student_record.py::run_assessment_pipeline (without importing it)."""
    from src.alignment import AlignmentEngine
    record_result = service.transcribe_file(wav_path)
    record_result.target_text = target_text
    return AlignmentEngine().process_result(record_result)


TARGET = "the cat sat on the mat"


def test_perfect_read(patched_asr, wav_factory):
    wav = wav_factory()
    with patched_asr(TARGET) as service:
        alignment = _run(service, wav, TARGET)

    assert isinstance(alignment, AlignmentResult)
    assert alignment.transcript_text == TARGET
    assert alignment.metrics.accuracy == 1.0
    assert alignment.errors == []
    assert len(alignment.word_segments) == len(TARGET.split())


def test_substitution_and_omission(patched_asr, wav_factory):
    # "cat" -> "dog" (substitution); "on" dropped (omission)
    transcript = "the dog sat the mat"
    wav = wav_factory()
    with patched_asr(transcript) as service:
        alignment = _run(service, wav, TARGET)

    assert alignment.metrics.accuracy < 1.0
    error_types = {e.error_type for e in alignment.errors}
    assert "substitution" in error_types
    assert "omission" in error_types


def test_word_segments_timestamps(patched_asr, wav_factory):
    wav = wav_factory()
    with patched_asr(TARGET) as service:
        result = service.transcribe_file(wav)

    assert len(result.word_segments) == len(TARGET.split())
    ends = [s.end_time for s in result.word_segments]
    assert ends == sorted(ends)  # non-decreasing
    assert result.metadata["duration_s"] > 0


def test_missing_token_raises(wav_factory, monkeypatch):
    """Without the mock, transcribe_file must enforce the HF token guard."""
    monkeypatch.delenv("HUGGING_FACE_HUB_TOKEN", raising=False)
    service = WhisperASRService()
    with pytest.raises(ValueError, match="HUGGING_FACE_HUB_TOKEN"):
        service.transcribe_file(wav_factory())
