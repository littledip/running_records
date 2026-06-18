"""Audio recording utilities for the Running Record pipeline."""

import os
import tempfile
import threading
from typing import List, Optional

import numpy as np
import sounddevice as sd
import soundfile as sf


# Common sample rates for speech recognition
SAMPLE_RATES = {
    "whisper": 16000,      # Whisper expects 16kHz
    "standard": 44100,     # Standard audio quality
}


def get_default_sample_rate() -> int:
    """Return the sample rate Whisper expects."""
    return SAMPLE_RATES["whisper"]


def list_audio_devices() -> None:
    """Print available audio input devices for debugging."""
    print("Available audio devices:")
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        if isinstance(dev, dict):
            name = dev.get("name", "Unknown")
            max_input_channels = dev.get("max_input_channels", 0)
        else:
            name = getattr(dev, "name", "Unknown")
            max_input_channels = getattr(dev, "max_input_channels", 0)
        if max_input_channels > 0:
            print(f"  [{i}] {name} (inputs: {max_input_channels})")


class _AudioBuffer:
    """Thread-safe audio buffer that accumulates chunks from the stream callback.

    Usage:
        buffer = _AudioBuffer()
        # In the stream callback: buffer.append(indata)
        # When done: buffer.stop()
        # Then: _finalize_recording(buffer.chunks, ...)
    """

    def __init__(self) -> None:
        self.chunks: List[np.ndarray] = []
        self._stop_flag = threading.Event()

    def append(self, indata: np.ndarray) -> None:
        """Append an audio chunk if the buffer hasn't been stopped."""
        if not self._stop_flag.is_set():
            self.chunks.append(indata.copy())

    def stop(self) -> None:
        """Signal the buffer to stop accepting new chunks."""
        self._stop_flag.set()


def _finalize_recording(
    chunks: List[np.ndarray],
    sample_rate: int,
    output_path: Optional[str] = None,
) -> str:
    """Concatenate audio chunks, validate duration, and write to a WAV file.

    Args:
        chunks: List of numpy arrays containing float32 audio data.
        sample_rate: Sample rate in Hz.
        output_path: Output file path. If None, creates a temp file.

    Returns:
        Path to the saved WAV file.

    Raises:
        RuntimeError: If no chunks provided or recording is shorter than 1 second.
    """
    if not chunks:
        raise RuntimeError("No audio was recorded. Check your microphone settings.")

    audio_data = np.concatenate(chunks, axis=0)

    min_samples = sample_rate  # At least 1 second of audio
    if len(audio_data) < min_samples:
        duration_sec = len(audio_data) / sample_rate
        raise RuntimeError(
            f"Recording too short ({duration_sec:.1f}s). "
            f"Please speak for at least 1 second."
        )

    if output_path is None:
        fd, output_path = tempfile.mkstemp(
            suffix=".wav", prefix="rr_recording_"
        )
        os.close(fd)

    try:
        sf.write(output_path, audio_data, sample_rate)
    except Exception as e:
        if os.path.exists(output_path):
            os.unlink(output_path)
        raise RuntimeError(f"Failed to save audio file: {e}") from e

    duration = len(audio_data) / sample_rate
    print(f"✅ Saved recording to: {output_path} ({duration:.1f}s)")
    return output_path


def record_audio(
    duration_seconds: float = 15.0,
    sample_rate: Optional[int] = None,
    output_path: Optional[str] = None,
) -> str:
    """Record audio from the default microphone for a fixed duration.

    Args:
        duration_seconds: How long to record in seconds.
        sample_rate: Sample rate (defaults to 16000 for Whisper compatibility).
        output_path: Optional path to save the file. If None, uses a temp file.

    Returns:
        Path to the saved WAV file.

    Raises:
        RuntimeError: If no microphone is available or recording fails.
    """
    if sample_rate is None:
        sample_rate = get_default_sample_rate()

    print(f"🎤 Recording for {duration_seconds} seconds...")
    print("   Speak now, then press Enter to stop early.")

    try:
        audio_data = sd.rec(
            int(duration_seconds * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
        )
        sd.wait()
    except KeyboardInterrupt:
        print("\n⏹️  Recording interrupted by user.")
        audio_data = None

    if audio_data is None or len(audio_data) == 0:
        raise RuntimeError("No audio was recorded. Check your microphone settings.")

    return _finalize_recording([audio_data], sample_rate, output_path)


def record_audio_with_stop(
    sample_rate: Optional[int] = None,
    output_path: Optional[str] = None,
) -> str:
    """Record audio until the user presses Enter to stop.

    Args:
        sample_rate: Sample rate (defaults to 16000).
        output_path: Optional path to save the file.

    Returns:
        Path to the saved WAV file.
    """
    if sample_rate is None:
        sample_rate = get_default_sample_rate()

    print("🎤 Recording... Press Enter when you're done speaking.")
    print("   (Minimum 1 second of audio will be recorded)")

    buffer = _AudioBuffer()

    def _record_loop() -> None:
        """Run the audio stream in a background thread."""
        with sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
            callback=lambda indata, frames, time_info, status: buffer.append(indata),
        ):
            while not buffer._stop_flag.is_set():
                sd.sleep(100)

    recorder_thread = threading.Thread(target=_record_loop, daemon=True)
    recorder_thread.start()

    try:
        input("Press Enter to stop recording...")
    except KeyboardInterrupt:
        print("\n⏹️  Recording interrupted.")

    buffer.stop()
    recorder_thread.join(timeout=2.0)

    return _finalize_recording(buffer.chunks, sample_rate, output_path)


def delete_audio_file(path: str) -> None:
    """Safely delete an audio file, ignoring non-critical errors."""
    try:
        if os.path.exists(path):
            os.unlink(path)
            print(f"🗑️  Deleted temporary file: {path}")
    except OSError:
        pass
