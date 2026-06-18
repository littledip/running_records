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
                time_offset += parsed.metadata.get("total_duration_s", 0.0)
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
            
            # Handle both word-level timestamps (chunks) and segment-level timestamps
            chunks = whisper_result.get("chunks", [])
            
            if chunks:
                # Word-level timestamps: each chunk has {"text": "...", "timestamp": (start, end)}
                for chunk in chunks:
                    chunk_text = chunk["text"].strip()
                    if not chunk_text:
                        continue
                    
                    timestamp = chunk.get("timestamp")
                    if isinstance(timestamp, (list, tuple)) and len(timestamp) == 2:
                        start_time = timestamp[0] + offset
                        end_time = timestamp[1] + offset
                    else:
                        start_time = offset
                        end_time = offset
                    
                    # Split chunk text into individual words for finer alignment
                    words_in_chunk = chunk_text.split()
                    if len(words_in_chunk) == 1:
                        # Single word in this chunk — use the full timestamp
                        segments.append(WordSegment(
                            word=words_in_chunk[0],
                            start_time=start_time,
                            end_time=end_time,
                            confidence=chunk.get("probability", 0.9)
                        ))
                    else:
                        # Multiple words in this chunk — distribute the timestamp evenly
                        duration = end_time - start_time
                        for i, word in enumerate(words_in_chunk):
                            word_start = start_time + (i * duration / len(words_in_chunk))
                            word_end = start_time + ((i + 1) * duration / len(words_in_chunk))
                            segments.append(WordSegment(
                                word=word,
                                start_time=word_start,
                                end_time=word_end,
                                confidence=chunk.get("probability", 0.9)
                            ))
            else:
                # Fallback for non-word-level outputs or older versions
                for seg in whisper_result.get("segments", []):
                    segments.append(WordSegment(
                        word=seg["text"].strip(),
                        start_time=seg["start"] + offset,
                        end_time=seg["end"] + offset,
                        confidence=0.95
                    ))

            # Calculate total duration from all segments
            if segments:
                total_duration = segments[-1].end_time - segments[0].start_time
            else:
                total_duration = 0.0

            return RunningRecordResult(
                target_text="",
                transcript_text=text,
                word_segments=segments,
                metadata={
                    "duration_s": total_duration,
                    "model": self.model_name,
                    "total_duration_s": total_duration
                }
            )
        except Exception as e:
            raise RuntimeError(f"ASR parsing failed: {e}") from e
