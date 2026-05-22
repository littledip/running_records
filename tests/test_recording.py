"""Tests for the audio recording module."""

import os
import tempfile
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import soundfile as sf

from src.recording import (
    _AudioBuffer,
    _finalize_recording,
    record_audio,
    record_audio_with_stop,
    delete_audio_file,
    get_default_sample_rate,
)


class TestAudioBuffer:
    """Tests for the _AudioBuffer class — pure logic, no hardware."""

    def test_append_adds_chunk(self):
        buffer = _AudioBuffer()
        chunk = np.array([0.1, 0.2, 0.3], dtype="float32")
        buffer.append(chunk)
        assert len(buffer.chunks) == 1
        np.testing.assert_array_equal(buffer.chunks[0], chunk)

    def test_append_ignores_after_stop(self):
        buffer = _AudioBuffer()
        buffer.stop()
        buffer.append(np.array([0.1], dtype="float32"))
        assert len(buffer.chunks) == 0

    def test_multiple_chunks_accumulate(self):
        buffer = _AudioBuffer()
        chunk1 = np.array([0.1, 0.2], dtype="float32")
        chunk2 = np.array([0.3, 0.4], dtype="float32")
        buffer.append(chunk1)
        buffer.append(chunk2)
        assert len(buffer.chunks) == 2

    def test_chunks_are_copies_not_references(self):
        """Ensure appended chunks are deep copies — mutating the original
        should not affect the buffer."""
        buffer = _AudioBuffer()
        chunk = np.array([0.1, 0.2], dtype="float32")
        buffer.append(chunk)
        chunk[0] = 999.0
        assert buffer.chunks[0][0] == 0.1

    def test_stop_sets_event_flag(self):
        buffer = _AudioBuffer()
        assert not buffer._stop_flag.is_set()
        buffer.stop()
        assert buffer._stop_flag.is_set()


class TestFinalizeRecording:
    """Tests for _finalize_recording — pure logic, no hardware."""

    def test_single_chunk_saved_to_temp_file(self):
        sample_rate = 16000
        duration = 2.0
        audio_data = np.random.randn(int(sample_rate * duration)).astype("float32")

        result_path = _finalize_recording([audio_data], sample_rate)

        assert os.path.exists(result_path)
        assert result_path.endswith(".wav")
        assert "rr_recording_" in result_path
        os.unlink(result_path)

    def test_multiple_chunks_concatenated(self):
        sample_rate = 16000
        chunk1 = np.random.randn(int(sample_rate * 1.5)).astype("float32")
        chunk2 = np.random.randn(int(sample_rate * 1.5)).astype("float32")

        result_path = _finalize_recording([chunk1, chunk2], sample_rate)

        loaded_data, loaded_sr = sf.read(result_path)
        assert len(loaded_data) == len(chunk1) + len(chunk2)
        assert loaded_sr == sample_rate
        os.unlink(result_path)

    def test_custom_output_path(self):
        sample_rate = 16000
        audio_data = np.random.randn(int(sample_rate * 2.0)).astype("float32")

        fd, custom_path = tempfile.mkstemp(suffix=".wav", prefix="test_")
        os.close(fd)

        result_path = _finalize_recording([audio_data], sample_rate, custom_path)

        assert result_path == custom_path
        assert os.path.exists(custom_path)
        os.unlink(custom_path)

    def test_empty_chunks_raises_error(self):
        with pytest.raises(RuntimeError, match="No audio was recorded"):
            _finalize_recording([], 16000)

    def test_too_short_recording_raises_error(self):
        sample_rate = 16000
        short_chunk = np.random.randn(100).astype("float32")  # ~0.006s

        with pytest.raises(RuntimeError, match="Recording too short"):
            _finalize_recording([short_chunk], sample_rate)

    def test_deleted_on_write_failure_with_explicit_path(self):
        """When an explicit (invalid) path is given and write fails,
        no file exists to clean up — but the error is still raised."""
        audio_data = np.random.randn(16000).astype("float32")

        with pytest.raises(RuntimeError, match="Failed to save audio file"):
            _finalize_recording([audio_data], 16000, "/nonexistent/dir/output.wav")

    def test_temp_file_cleaned_up_on_write_failure(self):
        """When output_path is None (temp file created) and write fails,
        the temp file must be deleted."""
        audio_data = np.random.randn(16000).astype("float32")

        with patch("src.recording.sf.write", side_effect=IOError("disk full")):
            with pytest.raises(RuntimeError, match="Failed to save audio file"):
                _finalize_recording([audio_data], 16000)


class TestRecordAudio:
    """Tests for record_audio — mocked hardware."""

    @patch("src.recording.sd")
    def test_records_and_saves_file(self, mock_sd):
        sample_rate = 16000
        duration = 3.0
        mock_audio = np.random.randn(int(sample_rate * duration)).astype("float32")

        mock_sd.rec.return_value = mock_audio
        mock_sd.wait.return_value = None

        result_path = record_audio(duration_seconds=duration, sample_rate=sample_rate)

        assert os.path.exists(result_path)
        assert "rr_recording_" in result_path
        mock_sd.rec.assert_called_once()
        os.unlink(result_path)

    @patch("src.recording.sd")
    def test_keyboard_interrupt_raises_error(self, mock_sd):
        mock_sd.rec.side_effect = KeyboardInterrupt()

        with pytest.raises(RuntimeError, match="No audio was recorded"):
            record_audio(sample_rate=16000)


class TestRecordAudioWithStop:
    """Tests for record_audio_with_stop — mocked hardware."""

    @patch("src.recording.sd.InputStream")
    @patch("src.recording._finalize_recording")
    def test_calls_finalize_with_buffer_chunks(self, finalize_mock, mock_stream, monkeypatch):
        """Verify the overall flow completes and _finalize_recording is called."""
        sample_rate = 16000

        # Mock InputStream as a no-op context manager
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_stream.return_value = mock_instance

        test_path = "/tmp/test_recording.wav"
        finalize_mock.return_value = test_path

        # input() returns immediately (user pressed Enter)
        monkeypatch.setattr("builtins.input", lambda x: "")

        result_path = record_audio_with_stop(sample_rate=sample_rate)

        assert result_path == test_path
        finalize_mock.assert_called_once()

        # Verify _finalize_recording received a list and the sample rate
        call_args = finalize_mock.call_args
        chunks_arg = call_args[0][0]
        sr_arg = call_args[0][1]
        assert isinstance(chunks_arg, list)
        assert sr_arg == sample_rate

    @patch("src.recording.sd.InputStream")
    @patch("src.recording._finalize_recording")
    def test_keyboard_interrupt_stops_gracefully(self, finalize_mock, mock_stream, monkeypatch):
        """Verify KeyboardInterrupt doesn't crash the recording."""
        # Mock InputStream as a no-op context manager
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_stream.return_value = mock_instance

        finalize_mock.return_value = "/tmp/test.wav"

        # input() raises KeyboardInterrupt
        monkeypatch.setattr(
            "builtins.input", lambda x: (_ for _ in ()).throw(KeyboardInterrupt())
        )

        result_path = record_audio_with_stop(sample_rate=16000)

        assert result_path == "/tmp/test.wav"

class TestDeleteAudioFile:
    def test_deletes_existing_file(self, tmp_path):
        test_file = tmp_path / "test.wav"
        test_file.write_text("fake audio")

        delete_audio_file(str(test_file))

        assert not test_file.exists()

    def test_no_error_on_missing_file(self):
        delete_audio_file("/nonexistent/file.wav")  # Should not raise


class TestGetDefaultSampleRate:
    def test_returns_16000(self):
        assert get_default_sample_rate() == 16000
