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

def _pairs(engine, target, transcript):
    """Align and return (target, transcript) word pairs for assertions."""
    aligned_target, aligned_transcript = engine.align_texts(target, transcript)
    assert len(aligned_target) == len(aligned_transcript)
    return list(zip(aligned_target, aligned_transcript))


def test_align_single_mid_sentence_omission():
    # The only difference is the omitted word "mainly". Words after it
    # (in, the, plain.) recur, which the greedy aligner mishandles.
    engine = AlignmentEngine()
    pairs = _pairs(
        engine,
        "The rain in Spain stays mainly in the plain.",
        "The rain in Spain stays in the plain.",
    )

    omissions = [(t, tr) for t, tr in pairs if t != "" and tr == ""]
    insertions = [(t, tr) for t, tr in pairs if t == "" and tr != ""]
    matched = [(t, tr) for t, tr in pairs if t != "" and tr != ""]

    assert omissions == [("mainly", "")], f"expected only 'mainly' omitted, got {omissions}"
    assert insertions == [], f"expected no insertions, got {insertions}"
    assert all(t == tr for t, tr in matched), f"all aligned words should match, got {matched}"


def test_align_multiple_omissions():
    engine = AlignmentEngine()
    pairs = _pairs(engine, "the quick brown fox jumps", "the fox jumps")

    omissions = [t for t, tr in pairs if t != "" and tr == ""]
    insertions = [tr for t, tr in pairs if t == "" and tr != ""]

    assert omissions == ["quick", "brown"], f"got {omissions}"
    assert insertions == []


def test_align_single_insertion():
    engine = AlignmentEngine()
    pairs = _pairs(engine, "the cat sat", "the big cat sat")

    insertions = [tr for t, tr in pairs if t == "" and tr != ""]
    omissions = [t for t, tr in pairs if t != "" and tr == ""]

    assert insertions == ["big"], f"got {insertions}"
    assert omissions == []


def test_align_substitution_keeps_words_paired():
    # A substitution must stay a 1:1 pair, not split into omission + insertion.
    engine = AlignmentEngine()
    pairs = _pairs(engine, "the cat sat", "the bat sat")

    assert len(pairs) == 3, f"expected 3 aligned pairs, got {pairs}"
    assert ("cat", "bat") in pairs
    assert not any(t == "" or tr == "" for t, tr in pairs), f"no gaps expected, got {pairs}"


def test_omission_shift_does_not_create_word_order_errors():
    # A single omission shifts following words' positions by one. That is NOT
    # a reordering — no word-order errors should be produced.
    engine = AlignmentEngine()
    result = RunningRecordResult(
        target_text="The rain in Spain stays mainly in the plain.",
        transcript_text="The rain in Spain stays in the plain.",
        word_segments=[],
        metadata={"duration_s": 7.16},
    )
    alignment = engine.process_result(result)
    word_order = [e for e in alignment.errors if e.error_type == "word_order"]
    omissions = [e for e in alignment.errors if e.error_type == "omission"]

    assert word_order == [], f"omission shift must not create word-order errors, got {word_order}"
    assert [e.target_word for e in omissions] == ["mainly"], f"got {[e.target_word for e in omissions]}"


def test_genuine_transposition_flagged_as_word_order():
    # Reader swaps "the cat" -> "cat the": a real reordering.
    engine = AlignmentEngine()
    result = RunningRecordResult(
        target_text="the cat sat",
        transcript_text="cat the sat",
        word_segments=[],
        metadata={"duration_s": 1.0},
    )
    alignment = engine.process_result(result)
    types = [e.error_type for e in alignment.errors]

    assert "word_order" in types, f"expected a word-order error for a real swap, got {types}"


def test_error_count_matches_errors_list_for_transposition():
    # A transposition is two non-matching alignment cells but ONE word-order
    # error. The headline error_count must match the detailed list.
    engine = AlignmentEngine()
    result = RunningRecordResult(
        target_text="the cat sat",
        transcript_text="cat the sat",
        word_segments=[],
        metadata={"duration_s": 1.0},
    )
    alignment = engine.process_result(result)
    assert alignment.metrics.error_count == len(alignment.errors), \
        f"error_count={alignment.metrics.error_count} but list has {len(alignment.errors)}"


def test_error_count_matches_errors_list_for_omission():
    engine = AlignmentEngine()
    result = RunningRecordResult(
        target_text="the quick brown fox",
        transcript_text="the fox",
        word_segments=[],
        metadata={"duration_s": 1.0},
    )
    alignment = engine.process_result(result)
    assert alignment.metrics.error_count == len(alignment.errors)


def test_homophone_is_not_a_substitution():
    # True homophones (identical in speech, indistinguishable to ASR) must not
    # be flagged as reading errors.
    engine = AlignmentEngine()
    error = engine.classify_error("plane", "plain")
    assert error.error_type != "substitution", f"homophone flagged as {error.error_type}"


def test_homophone_produces_no_error_in_pipeline():
    engine = AlignmentEngine()
    result = RunningRecordResult(
        target_text="The rain in Spain stays mainly in the plain.",
        transcript_text="The rain in Spain stays in the plane.",
        word_segments=[],
        metadata={"duration_s": 7.16},
    )
    alignment = engine.process_result(result)
    substitutions = [e for e in alignment.errors if e.error_type == "substitution"]
    assert substitutions == [], f"plain/plane should not be a substitution, got {substitutions}"


def test_accuracy_derived_from_error_count_homophone():
    # Accuracy = (running words - errors) / running words. Homophone is not an
    # error, so a 9-word passage with one omission is 8/9, not the old 7/9.
    engine = AlignmentEngine()
    result = RunningRecordResult(
        target_text="The rain in Spain stays mainly in the plain.",
        transcript_text="The rain in Spain stays in the plane.",
        word_segments=[],
        metadata={"duration_s": 7.16},
    )
    alignment = engine.process_result(result)
    assert alignment.metrics.error_count == 1
    assert abs(alignment.metrics.accuracy - 8 / 9) < 1e-9, f"got {alignment.metrics.accuracy}"


def test_accuracy_consistent_with_errors_transposition():
    engine = AlignmentEngine()
    result = RunningRecordResult(
        target_text="the cat sat",
        transcript_text="cat the sat",
        word_segments=[],
        metadata={"duration_s": 1.0},
    )
    alignment = engine.process_result(result)
    # 3 running words, 1 word-order error → 2/3.
    assert abs(alignment.metrics.accuracy - 2 / 3) < 1e-9, f"got {alignment.metrics.accuracy}"


def test_total_words_is_passage_length_not_alignment_cells():
    # A transposition produces 4 alignment cells but the passage is 3 words.
    engine = AlignmentEngine()
    result = RunningRecordResult(
        target_text="the cat sat",
        transcript_text="cat the sat",
        word_segments=[],
        metadata={"duration_s": 1.0},
    )
    alignment = engine.process_result(result)
    assert alignment.metrics.total_words == 3


def test_accuracy_clamped_at_zero_with_excess_insertions():
    engine = AlignmentEngine()
    result = RunningRecordResult(
        target_text="cat",
        transcript_text="cat cat cat cat",
        word_segments=[],
        metadata={"duration_s": 1.0},
    )
    alignment = engine.process_result(result)
    assert alignment.metrics.accuracy >= 0.0


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
