import pytest
from src.alignment import AlignmentEngine
from src.models import WordSegment, RunningRecordResult, ErrorType, AlignmentMetrics


def test_align_texts_basic():
    engine = AlignmentEngine()
    target = "the cat sat on the mat"
    transcript = "the bat sat on the mat"
    
    aligned_target, aligned_transcript = engine.align_texts(target, transcript)
    
    assert len(aligned_target) == len(aligned_transcript), \
        f"Alignment lengths must match: target={len(aligned_target)}, transcript={len(aligned_transcript)}"

def test_classify_error_substitution():
    engine = AlignmentEngine()
    error = engine.classify_error("cat", "bat")
    assert error.error_type == "substitution"
    assert error.confidence >= 0.90

def test_classify_error_omission():
    engine = AlignmentEngine()
    # Target word missing from transcript → omission
    error = engine.classify_error("the", "")
    assert error.error_type == "omission"

def test_classify_error_insertion():
    engine = AlignmentEngine()
    # Extra word in transcript not in target → insertion
    error = engine.classify_error("", "extra")
    assert error.error_type == "insertion"

def test_classify_error_homophone():
    engine = AlignmentEngine(phonetic_threshold=0.75)
    error = engine.classify_error("cat", "bat")
    assert error.error_type == "substitution"

def test_calculate_metrics_accuracy():
    engine = AlignmentEngine()  # ← Fixed: was missing this line
    result = RunningRecordResult(
        target_text="the cat sat",
        transcript_text="the bat sat",
        word_segments=[
            WordSegment(word="the", start_time=0.0, end_time=0.3, confidence=1.0),
            WordSegment(word="cat", start_time=0.4, end_time=0.7, confidence=0.85),  # Error
            WordSegment(word="sat", start_time=0.8, end_time=1.1, confidence=1.0)
        ],
        metadata={"duration_s": 1.3}
    )
    
    metrics = engine.calculate_metrics(result)
    assert metrics.accuracy < 0.95  # One out of three words is an error
    assert metrics.wpm > 0

def test_process_result_full_pipeline():
    engine = AlignmentEngine()
    
    result = RunningRecordResult(
        target_text="The quick brown fox",
        transcript_text="The quick brown dog",
        word_segments=[
            WordSegment(word="the", start_time=0.0, end_time=0.2, confidence=1.0),
            WordSegment(word="quick", start_time=0.3, end_time=0.6, confidence=1.0),
            WordSegment(word="brown", start_time=0.7, end_time=1.0, confidence=1.0),
            WordSegment(word="dog", start_time=1.1, end_time=1.4, confidence=1.0)  # Substitution
        ],
        metadata={"duration_s": 1.5}
    )
    
    alignment = engine.process_result(result)
    
    assert isinstance(alignment.errors, list)
    assert len(alignment.errors) > 0
    assert alignment.metrics.accuracy < 1.0

def test_reading_rate_variance():
    result = RunningRecordResult(
        target_text="test",
        transcript_text="test",
        word_segments=[
            WordSegment(word="test", start_time=0.0, end_time=0.5, confidence=1.0)
        ],
        metadata={"duration_s": 0.5}
    )
    
    engine = AlignmentEngine()
    metrics = engine.calculate_metrics(result)
    
    assert isinstance(metrics.reading_rate_variance, float)
    assert metrics.reading_rate_variance >= 0.0
