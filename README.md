# Running Record — ASR Pipeline & Alignment Engine

An automated **Running Record** assessment system that uses speech recognition to evaluate reading accuracy. A student reads a passage aloud; the system records the audio, transcribes it with Whisper, compares it against the target text, classifies miscues, and presents the results in a multi-page Streamlit dashboard.

## Features

- 🎤 **In-App Recording** — Capture microphone input directly in the browser flow via `sounddevice` (recorded on the machine running Streamlit)
- 🗣️ **Whisper Transcription** — Word-level ASR using the `openai/whisper-medium` model through 🤗 Transformers
- 🔍 **Alignment Engine** — Fuzzy matching with error classification:
  - **Substitution** — Wrong word spoken
  - **Omission** — Word skipped
  - **Insertion** — Extra word added
  - **Self-Correction** — Word attempted then corrected
  - **Word Order** — Words present but in wrong sequence
- 📊 **Metrics** — Accuracy %, WPM, total words, error counts
- 🖥️ **Multi-Page Streamlit App** — Student assessment flow, results visualization, and a teacher dashboard
- 💾 **Record Persistence** — Each assessment is saved as JSON under `data/records/` for later review and CSV export

## Project Structure

```
running_records/
├── Running_Record.py             # App entry point ("Running Record" launcher page)
├── pages/                        # Streamlit multi-page views
│   ├── Student_Record.py         # Recording + transcription + analysis flow
│   ├── Student_Results.py        # Per-student results (metrics, highlights, charts)
│   └── Teacher_Dashboard.py      # Teacher dashboard: passages, records, analytics
├── src/                          # UI-agnostic core (no Streamlit imports)
│   ├── alignment.py              # Alignment engine + error classification
│   ├── assessment.py             # Orchestration: transcribe→align + record building
│   ├── audio_utils.py            # Secure temp file handling + audio chunking
│   ├── config.py                 # Central paths, model name, token lookup
│   ├── models.py                 # Pydantic data contracts (shared)
│   ├── passages.py               # Passage manifest load/lookup/save/delete
│   ├── pipeline.py               # Whisper ASR service
│   ├── recording.py              # Microphone recording utilities (CLI demo)
│   └── storage.py                # Assessment-record repository (data/records)
├── utils.py                      # Error labels/colors, text highlighting, charts
├── passages.json                 # Reading passages manifest
├── data/records/                 # Saved assessment results (created at runtime)
├── tests/                        # Test suite
│   ├── test_alignment.py         # Alignment engine tests
│   ├── test_assessment.py        # Orchestration + record-building tests
│   ├── test_e2e_pipeline.py      # transcribe→align with Whisper mocked
│   ├── test_integration_tracks.py# Pipeline → alignment integration tests
│   ├── test_models.py            # Model validation tests
│   ├── test_passages.py          # Passage manifest tests
│   ├── test_pipeline.py          # Pipeline tests
│   ├── test_real_asr.py          # Opt-in real-model test (skipped by default)
│   ├── test_recording.py         # Recording module tests
│   └── test_storage.py           # Record repository tests
├── scripts/                      # CLI utilities
│   ├── demo_pipeline.py          # Record + transcribe + analyze demo
│   ├── debug_recording.py        # Recording debug helper
│   └── verify_pipeline.py        # Opt-in real-model verification harness
├── requirements.txt              # Python dependencies
├── pytest.ini                    # Test configuration
└── .env.example                  # Environment variable template
```

## How It Works

```
Running Record (Running_Record.py)
  └─▶ "Start Student Assessment" ─▶ pick a passage ─▶ Confirm
        └─▶ Student Record (pages/Student_Record.py)
              ├─ Start / Stop microphone recording (sounddevice, background thread)
              ├─ Transcribe WAV with Whisper (src/pipeline.py)
              ├─ Align transcript vs. target text (src/alignment.py)
              ├─ Save result JSON ─▶ data/records/
              └─▶ Student Results (pages/Student_Results.py)

Teacher Dashboard (sidebar nav) ─▶ pages/Teacher_Dashboard.py
        ├─ Passages   — add / edit / delete entries in passages.json
        ├─ Records    — browse, filter, sort, and export saved assessments
        └─ Analytics  — aggregate accuracy/miscue metrics + system status
```

Session-state guards enforce the flow: the **Student Record** page refuses to run until an assessment is started from Home, and the **Teacher Dashboard** blocks access while an assessment is active.

## Installation

### Prerequisites

- **Python 3.11+** (see `.python-version`)
- **ffmpeg** — Required for Whisper to decode audio files
  - macOS: `brew install ffmpeg`
  - Ubuntu/Debian: `apt-get install ffmpeg`
  - Windows: Download from [ffmpeg.org](https://ffmpeg.org/download.html)
- A working **microphone** on the machine that runs the app (recording happens server-side via `sounddevice`)

### Setup

```bash
# Navigate to project directory
cd /Users/johnd/projects/running_records

# Create virtual environment
python3 -m venv app_env
source app_env/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Hugging Face token (required)

The ASR pipeline reads `HUGGING_FACE_HUB_TOKEN` from the environment and raises an error if it is missing. The app does **not** auto-load `.env`, so export the token in your shell before launching:

```bash
cp .env.example .env
# Edit .env and set: HUGGING_FACE_HUB_TOKEN=hf_xxxxxx

# Export it into the current shell (the app reads it from the environment)
export $(grep -v '^#' .env | xargs)
```

Get a free token at https://huggingface.co/settings/tokens (read permission is sufficient).

## Usage

### Streamlit App

Launch the multi-page web interface:

```bash
source app_env/bin/activate
streamlit run Running_Record.py
```

Then, in the browser:

1. **Running Record** → click **🎤 Start Student Assessment**, choose a passage, and confirm.
2. **Student Record** → click **Start**, read the passage aloud, then **Stop**. The app transcribes, aligns, saves the result, and redirects to results.
3. **Student Results** → review accuracy, WPM, total words, error count, highlighted text comparison, and an error breakdown chart.
4. **Teacher Dashboard** → manage passages, browse/export saved records, and view aggregate analytics.

### Quick Demo (CLI)

Record yourself reading from the command line, then get instant results:

```bash
source app_env/bin/activate
python scripts/demo_pipeline.py

# List available microphones
python scripts/demo_pipeline.py --list-devices

# Record for 30 seconds with a specific target text
python scripts/demo_pipeline.py --duration 30 --target "The cat sat on the mat"
```

### Passages

Passages are stored in `passages.json`. The default ships as a list of objects:

```json
[
  { "id": 1, "title": "The Rain in Spain", "text": "The rain in Spain stays mainly in the plain." }
]
```

The app accepts both the list form above and a dict-keyed form. New passages added through the Teacher Dashboard are written back to this file.

### Assessment Records

Each completed assessment is written to `data/records/<student_id>_<timestamp>.json` with fields such as `student_id`, `passage_id`, `timestamp`, `accuracy_pct`, `miscue_count`, `word_error_rate`, and `transcript`. The Teacher Dashboard reads this directory to populate the Records and Analytics tabs.

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

### Verifying the transcribe→align path

The microphone step can't run in CI, but you can feed a sample `.wav` straight
through `transcribe → align` two ways:

```bash
# Fast & deterministic — Whisper is mocked, no token or model download needed.
# Runs as part of the normal suite.
pytest tests/test_e2e_pipeline.py -v

# Real model end-to-end — synthesizes speech with macOS `say` + ffmpeg, then runs
# the actual whisper-medium model. Needs HUGGING_FACE_HUB_TOKEN exported.
export $(grep -v '^#' .env | xargs)
python scripts/verify_pipeline.py
python scripts/verify_pipeline.py --text "The rain in Spain stays mostly in the plane."  # introduce miscues
python scripts/verify_pipeline.py --wav my_reading.wav                                    # use your own audio

# The same real-model check as an opt-in test (skipped by default):
RUN_REAL_ASR=1 pytest -m integration -v
```

### Test Coverage

| Module | Tests | Description |
|---|---|---|
| `test_models.py` | 3 | Pydantic model validation |
| `test_pipeline.py` | 3 | Secure temp files, Whisper output parsing, audio chunking |
| `test_alignment.py` | 8 | Text alignment, error classification, metrics calculation |
| `test_recording.py` | 19 | Audio buffer, file I/O, hardware mocking |
| `test_integration_tracks.py` | 5 | Pipeline → alignment integration, metrics & serialization |

**Total: 38 tests passing** ✅

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
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Microphone   │────▶│ Recording    │────▶│ WAV File     │
│ (sounddevice)│     │ (bg thread)  │     │ (temp .wav)  │
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                 │
                                                 ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Whisper      │────▶│ Alignment    │────▶│ Result JSON  │
│ Pipeline     │     │ Engine       │     │ data/records │
│ (ASR)        │     │ (classify)   │     └──────┬───────┘
└──────────────┘     └──────────────┘            │
        ▲                                         ▼
        │                              ┌──────────────────────┐
        │                              │ Streamlit Multi-Page  │
        └──────────────────────────────│ Home / Record /       │
                                       │ Results / Teacher     │
                                       └──────────────────────┘
```

## Dependencies

| Package | Purpose |
|---|---|
| `transformers` + `torch` | Whisper model loading and inference |
| `sounddevice` + `soundfile` | Microphone recording and WAV I/O |
| `rapidfuzz` | Fuzzy string matching for alignment |
| `pydantic` | Data validation and serialization |
| `numpy` | Audio array manipulation |
| `streamlit` | Multi-page web dashboard |
| `pandas` + `altair` | Tables and charts in the dashboard |
| `matplotlib` | Optional — accuracy-trend chart in the Analytics tab |

## License

MIT
