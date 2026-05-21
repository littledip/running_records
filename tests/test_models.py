import pytest
from src.models import RunningRecordResult, WordSegment

def test_word_segment_validation():
    ws = WordSegment(word="cat", start_time=0.1, end_time=0.3, confidence=0.95)
    assert ws.word == "cat"

def test_running_record_result_creation():
    rr = RunningRecordResult(
        target_text="The cat sat.",
        transcript_text="The bat sat.",
        word_segments=[WordSegment(word="the", start_time=0, end_time=0.2, confidence=1.0)],
        metadata={"duration_s": 2.0}
    )
    assert rr.transcript_text == "The bat sat."

def test_invalid_confidence_range():
    with pytest.raises(ValueError):
        WordSegment(word="test", start_time=0, end_time=1, confidence=1.5)
