"""Assessment orchestration — the transcribe→align flow and record building.

Moves `run_assessment_pipeline` out of pages/student_record.py into the core so
the UI is a thin caller and the flow is unit-testable. No Streamlit imports.
"""
import time
from typing import Optional

from .alignment import AlignmentEngine
from .config import DEFAULT_MODEL_NAME
from .models import AlignmentResult
from .pipeline import WhisperASRService


def run_assessment(
    audio_path: str,
    target_text: str,
    model_name: str = DEFAULT_MODEL_NAME,
) -> AlignmentResult:
    """Transcribe `audio_path`, align it against `target_text`, return the result."""
    asr_service = WhisperASRService(model_name=model_name)
    record_result = asr_service.transcribe_file(audio_path)
    record_result.target_text = target_text
    return AlignmentEngine().process_result(record_result)


def result_to_record(
    result: AlignmentResult,
    passage_id,
    student_id: str = "Unknown",
    student_name: Optional[str] = None,
) -> dict:
    """Build a JSON-serializable assessment record from an AlignmentResult.

    Reads the real metric fields (metrics.accuracy / error_count / total_words
    and transcript_text) rather than the nonexistent attributes the old inline
    code referenced, which always serialized 0/empty.
    """
    total_words = result.metrics.total_words or 0
    error_count = result.metrics.error_count or 0
    wer = (error_count / total_words) if total_words else 0.0
    return {
        "student_id": student_id,
        "student_name": student_name or student_id,
        "passage_id": passage_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "accuracy_pct": round(result.metrics.accuracy * 100, 1),
        "miscue_count": error_count,
        "word_error_rate": round(wer, 3),
        "transcript": result.transcript_text,
    }
