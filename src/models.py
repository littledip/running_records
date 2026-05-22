# src/models.py (Fixed)
from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any, Optional


class WordSegment(BaseModel):
    word: str = Field(..., min_length=1)
    start_time: float = Field(ge=0.0)
    end_time: float = Field(ge=0.0)
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("end_time")
    @classmethod
    def end_must_be_after_start(cls, v, info):
        if "start_time" in info.data and v < info.data["start_time"]:
            raise ValueError(f"end_time ({v}) must be >= start_time ({info.data['start_time']})")
        return v


class ErrorType(BaseModel):
    error_type: str = Field(..., pattern=r"^(substitution|omission|insertion|self_correction|unknown|word_order)$")
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = ""
    target_word: Optional[str] = None


class AlignmentMetrics(BaseModel):
    accuracy: float = Field(ge=0.0, le=1.0)
    wpm: float = Field(ge=0.0)
    reading_rate_variance: float = Field(ge=0.0)
    total_words: int = Field(ge=0)
    error_count: int = 0


class RunningRecordResult(BaseModel):
    target_text: str
    transcript_text: str
    word_segments: List[WordSegment]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AlignmentResult(BaseModel):
    target_text: str
    transcript_text: str
    word_segments: List[WordSegment]
    errors: List[ErrorType]
    metrics: AlignmentMetrics
