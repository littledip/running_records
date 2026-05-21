import os
from typing import Optional, Dict, Any
import numpy as np
import torch
from transformers import pipeline
from .models import RunningRecordResult, WordSegment
from .audio_utils import write_secure_temp_wav, delete_secure_temp_file, split_audio_chunks

class WhisperASRService:
    def __init__(self, model_name: str = "openai/whisper-medium", device: Optional[str] = None):
        self.model_name = model_name
        # Auto-detect Apple Silicon vs CPU
        if device is None:
            self.device = "mps" if torch.backends.mps.is_available() else "cpu"
        else:
            self.device = device
        self._pipeline = None

    def _get_pipeline(self) -> pipeline:
        """Lazy-load the Whisper pipeline with secure token handling."""
        if self._pipeline is None:
            token = os.getenv("HUGGING_FACE_HUB_TOKEN")
            if not token:
                raise ValueError("Missing HUGGING_FACE_HUB_TOKEN environment variable.")
            
            print(f"🔄 Loading '{self.model_name}' on {self.device}...")
            self._pipeline = pipeline(
                "automatic-speech-recognition",
                model=self.model_name,
                device=0 if self.device == "mps" else -1,
                token=token,
                return_timestamps="word"  # Enables granular word-level alignment
            )
        return self._pipeline

    def transcribe_file(self, audio_path: str) -> RunningRecordResult:
        """Transcribe a single WAV file."""
        pipe = self._get_pipeline()
        result = pipe(audio_path)
        return self._parse_whisper_output(result)

    def transcribe_stream(self, audio_data: np.ndarray, sample_rate: int) -> RunningRecordResult:
        """Transcribe in-memory audio using chunked processing."""
        pipe = self._get_pipeline()
        all_segments = []
        time_offset = 0.0

        for chunk_data, sr in split_audio_chunks(audio_data, sample_rate):
            tmp_path = write_secure_temp_wav(chunk_data, sr)
            try:
                out = pipe(tmp_path)
                parsed = self._parse_whisper_output(out, offset=time_offset)
                all_segments.extend(parsed.word_segments)
                time_offset += parsed.metadata.get("duration_s", 0.0)
            finally:
                delete_secure_temp_file(tmp_path)

        return RunningRecordResult(
            target_text="",
            transcript_text=" ".join([s.word for s in all_segments]),
            word_segments=all_segments,
            metadata={"chunk_count": len(all_segments), "total_duration_s": time_offset}
        )

    def _parse_whisper_output(self, whisper_result: dict, offset: float = 0.0) -> RunningRecordResult:
        """Convert transformers output to our Pydantic contract with robust fallbacks."""
        try:
            text = whisper_result["text"].strip()
            segments = []
            
            for seg in whisper_result.get("segments", []):
                if "words" in seg and isinstance(seg["words"], list):
                    for w in seg["words"]:
                        segments.append(WordSegment(
                            word=w["word"].strip(),
                            start_time=w["start"] + offset,
                            end_time=w["end"] + offset,
                            confidence=w.get("probability", 0.9)
                        ))
                else:
                    # Fallback for non-word-level outputs or older versions
                    segments.append(WordSegment(
                        word=seg["text"].strip(),
                        start_time=seg["start"] + offset,
                        end_time=seg["end"] + offset,
                        confidence=0.95
                    ))

            if whisper_result.get("segments"):
                duration = whisper_result["segments"][-1]["end"] - whisper_result["segments"][0]["start"]
            else:
                duration = 0.0

            return RunningRecordResult(
                target_text="",
                transcript_text=text,
                word_segments=segments,
                metadata={"duration_s": duration, "model": self.model_name}
            )
        except Exception as e:
            raise RuntimeError(f"ASR parsing failed: {e}") from e
