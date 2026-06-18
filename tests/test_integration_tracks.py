# tests/test_integration_tracks.py
"""
Integration tests for Track 1 (ASR) → Track 2 (Alignment) flow.
Validates the full pipeline contract using RunningRecordResult -> AlignmentEngine.process_result()
"""
import pytest
from src.alignment import AlignmentEngine
from src.models import WordSegment, RunningRecordResult, AlignmentResult


# ──────────────────────────────────────────────────────────────
# Fixtures: Simulate Track 1 Output (RunningRecordResult)
# ──────────────────────────────────────────────────────────────
@pytest.fixture
def perfect_read_result():
    """Track 1 output: A flawless reading record."""
    return RunningRecordResult(
        target_text="The quick brown fox jumps over the lazy dog.",
        transcript_text="The quick brown fox jumps over the lazy dog.",
        word_segments=[
            WordSegment(word="the", start_time=0.0, end_time=0.3, confidence=1.0),
            WordSegment(word="quick", start_time=0.4, end_time=0.7, confidence=1.0),
            WordSegment(word="brown", start_time=0.8, end_time=1.1, confidence=1.0),
            WordSegment(word="fox", start_time=1.2, end_time=1.5, confidence=1.0),
            WordSegment(word="jumps", start_time=1.6, end_time=1.9, confidence=1.0),
            WordSegment(word="over", start_time=2.0, end_time=2.3, confidence=1.0),
            WordSegment(word="the", start_time=2.4, end_time=2.7, confidence=1.0),
            WordSegment(word="lazy", start_time=2.8, end_time=3.1, confidence=1.0),
            WordSegment(word="dog", start_time=3.2, end_time=3.5, confidence=1.0),
        ],
        metadata={"duration_s": 3.5}
    )

@pytest.fixture
def mixed_miscues_result():
    """Track 1 output: Substitution and omission."""
    return RunningRecordResult(
        target_text="The quick brown fox jumps over the lazy dog.",
        # Transcript is missing "fox" (omission) and has "slow" instead of "quick" (substitution)
        transcript_text="The slow brown jumps over the lazy dog.",
        word_segments=[
            WordSegment(word="the", start_time=0.0, end_time=0.3, confidence=1.0),
            WordSegment(word="slow", start_time=0.4, end_time=0.7, confidence=0.95), # Substitution
            WordSegment(word="brown", start_time=0.8, end_time=1.1, confidence=1.0),
            # Note: "fox" is missing from segments (omission)
            WordSegment(word="jumps", start_time=1.6, end_time=1.9, confidence=1.0),
            WordSegment(word="over", start_time=2.0, end_time=2.3, confidence=1.0),
            WordSegment(word="the", start_time=2.4, end_time=2.7, confidence=1.0),
            WordSegment(word="lazy", start_time=2.8, end_time=3.1, confidence=1.0),
            WordSegment(word="dog", start_time=3.2, end_time=3.5, confidence=1.0),
        ],
        metadata={"duration_s": 3.5}
    )

@pytest.fixture
def engine():
    return AlignmentEngine()


# ──────────────────────────────────────────────────────────────
# Integration Tests: Track 1 → Track 2 Flow
# ──────────────────────────────────────────────────────────────
class TestTrack1ToTrack2Integration:
    """Validates full pipeline contract: RunningRecordResult → AlignmentResult"""

    def test_perfect_read_contract_and_metrics(self, perfect_read_result, engine):
        # Call the actual method used in your codebase
        alignment = engine.process_result(perfect_read_result)

        # 1. Contract Validation
        assert isinstance(alignment, AlignmentResult), \
            f"Expected AlignmentResult, got {type(alignment)}"
        
        # 2. Metrics Validation
        assert alignment.metrics.accuracy == 1.0, "Perfect read should have 100% accuracy"
        assert len(alignment.errors) == 0, "Perfect read should have no errors"
        
        # 3. WPM Calculation (Words / Duration * 60)
        # 9 words in 3.5 seconds = ~154 WPM
        expected_wpm = (9 / 3.5) * 60
        assert abs(alignment.metrics.wpm - expected_wpm) < 5.0

    def test_mixed_miscues_error_detection(self, mixed_miscues_result, engine):
        alignment = engine.process_result(mixed_miscues_result)

        # 1. Contract Validation
        assert isinstance(alignment, AlignmentResult)
        
        # 2. Error Detection
        assert len(alignment.errors) >= 2, \
            f"Expected at least 2 errors (substitution + omission), got {len(alignment.errors)}"
        
        # 3. Verify Error Types are detected
        error_types = [str(e.error_type).lower() for e in alignment.errors]
        assert "substitution" in error_types, "Should detect 'slow' as substitution"
        assert "omission" in error_types, "Should detect missing 'fox' as omission"

    def test_metrics_math_consistency(self, mixed_miscues_result, engine):
        """
        Verifies that the engine's reported accuracy matches its internal formula:
        accuracy = (total_words - error_count) / total_words
        """
        alignment = engine.process_result(mixed_miscues_result)

        # Internal consistency check
        if alignment.metrics.total_words > 0:
            expected_acc = (alignment.metrics.total_words - alignment.metrics.error_count) / \
                           alignment.metrics.total_words
            
            assert abs(alignment.metrics.accuracy - expected_acc) < 0.01, \
                f"Accuracy mismatch: reported={alignment.metrics.accuracy}, calculated={expected_acc}"

    def test_pydantic_serialization_stability(self, perfect_read_result, engine):
        alignment = engine.process_result(perfect_read_result)

        # Ensure the output can be serialized to JSON (for dashboard/export)
        json_data = alignment.model_dump()
        
        assert "metrics" in json_data
        assert "errors" in json_data
        assert "target_text" in json_data
        
        # Round-trip validation
        restored = AlignmentResult.model_validate(json_data)
        assert restored.metrics.accuracy == alignment.metrics.accuracy

    def test_empty_transcript_handling(self, engine):
        """Test how the engine handles a completely failed read."""
        empty_result = RunningRecordResult(
            target_text="The quick brown fox.",
            transcript_text="", # Empty transcript
            word_segments=[],   # No segments
            metadata={"duration_s": 1.0}
        )
        
        alignment = engine.process_result(empty_result)
        
        assert isinstance(alignment, AlignmentResult)
        assert alignment.metrics.accuracy == 0.0
        assert len(alignment.errors) > 0, "Should detect all words as omissions"
