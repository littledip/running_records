"""Central configuration: paths, model, and credentials.

Single source of truth so pages and core modules stop recomputing PROJECT_ROOT
and hardcoding the model name. No Streamlit imports — this is UI-agnostic.
"""
import os
from pathlib import Path

# Project layout
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PASSAGES_FILE = PROJECT_ROOT / "passages.json"
ASSESSMENT_QUESTIONS_FILE = PROJECT_ROOT / "assessment_questions.json"
DATA_DIR = PROJECT_ROOT / "data"
RECORDS_DIR = DATA_DIR / "records"

# ASR model — overridable via env without code changes
DEFAULT_MODEL_NAME = os.getenv("RR_MODEL_NAME", "openai/whisper-medium")

# Assessment page: show the "Upload a recording" / "Generate with
# text-to-speech" source picker. Off by default — the page just
# auto-generates TTS for the selected passage.
SHOW_ASSESSMENT_AUDIO_SOURCE_PICKER = os.getenv(
    "RR_SHOW_ASSESSMENT_AUDIO_SOURCE_PICKER", "false"
).strip().lower() in ("1", "true", "yes")

# Credentials
HF_TOKEN_ENV = "HUGGING_FACE_HUB_TOKEN"


def get_hf_token() -> str | None:
    """Return the Hugging Face token from the environment, if set."""
    return os.getenv(HF_TOKEN_ENV)


def ensure_records_dir() -> Path:
    """Create the records directory if needed and return it."""
    RECORDS_DIR.mkdir(parents=True, exist_ok=True)
    return RECORDS_DIR
