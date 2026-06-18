"""Tests for assessment orchestration (src/assessment.py).

Uses the shared conftest fixtures (Whisper mocked at the _get_pipeline boundary,
real alignment) to exercise run_assessment and result_to_record.
"""
from src.assessment import run_assessment, result_to_record
from src.models import AlignmentResult

TARGET = "the cat sat on the mat"


def test_run_assessment_perfect_read(patched_asr, wav_factory):
    wav = wav_factory()
    with patched_asr(TARGET):
        result = run_assessment(wav, TARGET)
    assert isinstance(result, AlignmentResult)
    assert result.transcript_text == TARGET
    assert result.metrics.accuracy == 1.0
    assert result.errors == []


def test_run_assessment_detects_miscues(patched_asr, wav_factory):
    transcript = "the dog sat the mat"  # substitution + omission vs TARGET
    wav = wav_factory()
    with patched_asr(transcript):
        result = run_assessment(wav, TARGET)
    assert result.metrics.accuracy < 1.0
    assert {"substitution", "omission"} & {e.error_type for e in result.errors}


def test_result_to_record_fields(patched_asr, wav_factory):
    wav = wav_factory()
    with patched_asr(TARGET):
        result = run_assessment(wav, TARGET)
    record = result_to_record(result, passage_id=1, student_id="S1", student_name="Jane")
    assert record["student_id"] == "S1"
    assert record["student_name"] == "Jane"
    assert record["passage_id"] == 1
    assert record["accuracy_pct"] == 100.0
    assert record["miscue_count"] == 0
    assert record["word_error_rate"] == 0.0
    assert record["transcript"] == TARGET
    assert "timestamp" in record


def test_result_to_record_defaults_name_to_id(patched_asr, wav_factory):
    wav = wav_factory()
    with patched_asr(TARGET):
        result = run_assessment(wav, TARGET)
    record = result_to_record(result, passage_id=1, student_id="S2")
    assert record["student_name"] == "S2"


def test_result_to_record_alignment_round_trips(patched_asr, wav_factory):
    # The persisted 'alignment' must rebuild an AlignmentResult so the results
    # page can re-display after a refresh without re-running the model.
    wav = wav_factory()
    with patched_asr("the dog sat the mat"):
        result = run_assessment(wav, TARGET)
    record = result_to_record(result, passage_id=1, student_id="S1")
    restored = AlignmentResult.model_validate(record["alignment"])
    assert restored.metrics.accuracy == result.metrics.accuracy
    assert restored.transcript_text == result.transcript_text
    assert len(restored.errors) == len(result.errors)
