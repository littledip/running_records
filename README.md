# Running Record — ASR Pipeline & Alignment Engine

An automated **Running Record** assessment system that uses speech recognition to evaluate reading accuracy. Record a child reading aloud, and the system transcribes their speech, compares it against the target text, and identifies errors with detailed metrics.

## Features

- 🎤 **Audio Recording** — Capture microphone input via `sounddevice`
- 🗣️ **Whisper Transcription** — Word-level ASR using OpenAI's Whisper model (runs on Apple Silicon MPS or CPU)
- 🔍 **Alignment Engine** — Fuzzy matching with error classification:
  - **Substitution** — Wrong word spoken
  - **Omission** — Word skipped
  - **Insertion** — Extra word added
  - **Self-Correction** — Word attempted then corrected
  - **Word Order** — Words present but in wrong sequence
- 📊 **Metrics** — Accuracy %, WPM, total words, error counts
- 🖥️ **Streamlit Dashboard** — Visual interface with highlighted errors and charts

## Project Structure

```
running_records/
├── src/                          # Core source code
│   ├── alignment.py              # Alignment engine + error classification
│   ├── audio_utils.py            # Secure temp file handling + audio chunking
│   ├── models.py                 # Pydantic data contracts (shared)
│   ├── pipeline.py               # Whisper ASR service
│   └── recording.py              # Microphone recording utilities
├── tests/                        # Test suite (33 tests, all passing)
│   ├── test_alignment.py         # Alignment engine tests
│   ├── test_models.py            # Model validation tests
│   ├── test_pipeline.py          # Pipeline tests
│   └── test_recording.py         # Recording module tests
├── demo_pipeline.py              # CLI demo script
├── streamlit_app.py              # Web dashboard
├── requirements.txt              # Python dependencies
├── pytest.ini                    # Test configuration
└── .env.example                  # Environment variable template
```

## Installation

### Prerequisites

- **Python 3.11+** (see `.python-version`)
- **ffmpeg** — Required for Whisper to decode audio files
  - macOS: `brew install ffmpeg`
  - Ubuntu/Debian: Install via your package manager (`apt-get install ffmpeg`)
  - Windows: Download from [ffmpeg.org](https://ffmpeg.org/download.html)

### Setup

```bash
# Navigate to project directory
cd /Users/johnd/projects/running_records

# Create virtual environment
python3 -m venv app_env
source app_env/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set Hugging Face token (required for Whisper model access)
cp .env.example .env
# Edit .env and add your token: HUGGING_FACE_HUB_TOKEN=hf_xxxxxx
```

Get a free token at https://huggingface.co/settings/tokens (read permission is sufficient).

## Usage

### Quick Demo (CLI)

Record yourself reading, then get instant results:

```bash
source app_env/bin/activate
python demo_pipeline.py
```

Options:
```bash
# List available microphones
python demo_pipeline.py --list-devices

# Record for 30 seconds with a specific target text
python demo_pipeline.py --duration 30 --target "The cat sat on the mat"
```

### Streamlit Dashboard

Launch the web interface:

```bash
source app_env/bin/activate
streamlit run streamlit_app.py
```

Features:
- **Demo Mode** — Pre-loaded sample data to explore the interface
- **Upload Audio** — Upload .wav files and enter target text for custom assessments
- Visual error highlighting (color-coded by type)
- Metrics cards, bar charts, and detailed error tables

### Programmatic Usage

```python
from src.recording import record_audio_with_stop, delete_audio_file
from src.pipeline import WhisperASRService
from src.alignment import AlignmentEngine

# 1. Record audio
wav_path = record_audio_with_stop()

# 2. Transcribe
asr = WhisperASRService()
result = asr.transcribe_file(wav_path)

# 3. Align and classify errors
engine = AlignmentEngine()
alignment = engine.process_result(result)

# 4. Access results
print(f"Accuracy: {alignment.metrics.accuracy:.1%}")
print(f"WPM: {alignment.metrics.wpm:.1f}")
for error in alignment.errors:
    print(f"  [{error.error_type}] {error.reason}")

# 5. Clean up
delete_audio_file(wav_path)
```

## Testing

Run the full test suite:

```bash
source app_env/bin/activate
pytest tests/ -v
```

Run specific test files:
```bash
pytest tests/test_alignment.py -v
pytest tests/test_recording.py -v
```

### Test Coverage

| Module | Tests | Description |
|---|---|---|
| `test_models.py` | 3 | Pydantic model validation |
| `test_pipeline.py` | 3 | Secure temp files, Whisper output parsing, audio chunking |
| `test_alignment.py` | 8 | Text alignment, error classification, metrics calculation |
| `test_recording.py` | 19 | Audio buffer, file I/O, hardware mocking |

**Total: 33 tests passing** ✅

## Error Classification Details

The alignment engine uses fuzzy string matching (`rapidfuzz`) to compare transcribed words against the target text:

| Error Type | Condition | Confidence |
|---|---|---|
| **Insertion** | Word in transcript, not in target | 95% |
| **Omission** | Word in target, not in transcript | 90% |
| **Substitution** | Phonetically different words (ratio < 85%) | 92% |
| **Self-Correction** | Empty slots at same position | 85% |
| **Word Order** | Same word appears in wrong position | Detected via positional analysis |

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│ Microphone   │────▶│ Recording    │────▶│ WAV File    │
│ (sounddevice)│     │ Module       │     │ (.wav)      │
└─────────────┘     └──────────────┘     └──────┬──────┘
                                                │
                                                ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│ Streamlit    │◀────│ Alignment    │◀────│ Whisper     │
│ Dashboard    │     │ Engine       │     │ Pipeline    │
│ (visualize)  │     │ (classify)   │     │ (ASR)       │
└─────────────┘     └──────────────┘     └─────────────┘
```

## Dependencies

| Package | Purpose |
|---|---|
| `transformers` + `torch` | Whisper model loading and inference |
| `sounddevice` + `soundfile` | Microphone recording and WAV I/O |
| `rapidfuzz` | Fuzzy string matching for alignment |
| `pydantic` | Data validation and serialization |
| `numpy` | Audio array manipulation |
| `python-dotenv` | Environment variable loading |
| `streamlit` | Web dashboard (optional) |

## License

MIT
