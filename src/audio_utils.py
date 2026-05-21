import os
import tempfile
import numpy as np
from typing import Generator, Tuple
import soundfile as sf

def write_secure_temp_wav(audio_data: np.ndarray, sample_rate: int) -> str:
    """Write audio to a secure temp file with restricted permissions."""
    fd, path = tempfile.mkstemp(suffix=".wav", prefix="rr_audio_")
    os.close(fd)  # Close raw descriptor so Whisper can open it exclusively
    try:
        sf.write(path, audio_data, sample_rate)
    except Exception as e:
        if os.path.exists(path):
            os.unlink(path)
        raise RuntimeError(f"Failed to write secure temp WAV: {e}")
    return path

def delete_secure_temp_file(path: str) -> None:
    """Safely delete a temp file, ignoring non-critical errors."""
    try:
        if os.path.exists(path):
            os.unlink(path)
    except OSError:
        pass  # Graceful degradation for cleanup failures

def split_audio_chunks(audio_data: np.ndarray, sample_rate: int, chunk_duration_sec: float = 8.0) -> Generator[Tuple[np.ndarray, int], None, None]:
    """Yield fixed-duration chunks to manage memory during inference."""
    chunk_size = int(chunk_duration_sec * sample_rate)
    for i in range(0, len(audio_data), chunk_size):
        yield audio_data[i:i+chunk_size], sample_rate
