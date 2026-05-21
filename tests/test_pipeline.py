import os
import numpy as np
import pytest
from unittest.mock import patch, MagicMock
from src.pipeline import WhisperASRService
from src.audio_utils import write_secure_temp_wav, delete_secure_temp_file

def test_secure_temp_file_lifecycle():
    data = np.zeros(16000)  # 1 sec at 16kHz
    path = write_secure_temp_wav(data, 16000)
    assert os.path.exists(path)
    delete_secure_temp_file(path)
    assert not os.path.exists(path)

@patch.object(WhisperASRService, '_get_pipeline')
def test_parse_whisper_output_with_word_segments(mock_get_pipe):
    mock_pipe = MagicMock()
    mock_get_pipe.return_value = mock_pipe
    service = WhisperASRService(model_name="openai/whisper-medium")

    mock_output = {
        "text": "the cat sat",
        "segments": [
            {
                "start": 0.0, "end": 0.5, "text": "the ",
                "words": [{"word": "the", "start": 0.0, "end": 0.3, "probability": 0.98}]
            },
            {
                "start": 0.6, "end": 1.0, "text": "cat ",
                "words": [{"word": "cat", "start": 0.6, "end": 0.9, "probability": 0.92}]
            }
        ]
    }

    result = service._parse_whisper_output(mock_output)
    assert len(result.word_segments) == 2
    assert result.transcript_text == "the cat sat"
    assert result.metadata["duration_s"] > 0

def test_audio_chunking_logic():
    from src.audio_utils import split_audio_chunks
    sr = 16000
    audio = np.zeros(sr * 20)  # 20 seconds
    chunks = list(split_audio_chunks(audio, sr, chunk_duration_sec=5.0))
    assert len(chunks) == 4
