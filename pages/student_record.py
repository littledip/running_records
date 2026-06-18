import streamlit as st
import tempfile
import os
import time
import json
from pathlib import Path

from src.pipeline import WhisperASRService
from src.alignment import AlignmentEngine
from src.models import AlignmentResult

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PASSAGES_FILE = PROJECT_ROOT / "passages.json"
RECORDS_DIR = PROJECT_ROOT / "data" / "records"

# ───────── Session State & Guards ─────────
if "assessment_active" not in st.session_state:
    st.session_state["assessment_active"] = False


def reset_assessment_state():
    """Clear all assessment-related flags so no page gets wedged."""
    for key in ("assessment_active", "recording_in_progress", "is_recording",
                "recording_complete", "analysis_done"):
        st.session_state[key] = False
    st.session_state["current_passage_id"] = None


def guard_assessment():
    if not st.session_state.get("assessment_active", False):
        st.warning("🚫 Please start a new assessment from the Home page first.")
        return False
    return True


if not guard_assessment():
    st.stop()  # Prevents recording/analysis logic from running if guard fails


def run_assessment_pipeline(audio_path: str, target_text: str) -> AlignmentResult:
    asr_service = WhisperASRService()
    record_result = asr_service.transcribe_file(audio_path)
    record_result.target_text = target_text
    engine = AlignmentEngine()
    return engine.process_result(record_result)


def load_assigned_passage():
    """Return the passage dict assigned to this session, or None."""
    if not PASSAGES_FILE.exists():
        st.error("Passages file not found.")
        return None
    with open(PASSAGES_FILE, "r", encoding="utf-8") as f:
        passages = json.load(f)
    pid = st.session_state.get("current_passage_id")
    # Handle both list and dict manifest formats
    if isinstance(passages, list):
        return next((p for p in passages if p.get("id") == pid), None)
    return passages.get(pid)


def save_record(result: AlignmentResult, passage_id) -> Path:
    """Persist the assessment to data/records/ for the Teacher Dashboard."""
    RECORDS_DIR.mkdir(parents=True, exist_ok=True)
    total_words = result.metrics.total_words or 0
    error_count = result.metrics.error_count or 0
    wer = (error_count / total_words) if total_words else 0.0
    student_id = st.session_state.get("current_student_id", "Unknown")

    record = {
        "student_id": student_id,
        "student_name": st.session_state.get("current_student_name", student_id),
        "passage_id": passage_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "accuracy_pct": round(result.metrics.accuracy * 100, 1),
        "miscue_count": error_count,
        "word_error_rate": round(wer, 3),
        "transcript": result.transcript_text,
    }
    record_file = RECORDS_DIR / f"{student_id}_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(record_file, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
    return record_file


def main():
    st.title("🎤 Student Record")

    # 1. Resolve the assigned passage
    if not st.session_state.get("current_passage_id"):
        st.warning("No passage assigned. Please start an assessment from the Home page.")
        return

    passage = load_assigned_passage()
    if not passage:
        st.error(f"Assigned passage '{st.session_state.get('current_passage_id')}' not found.")
        return

    target_text = passage.get("text", "")
    st.markdown(f"**Reading Passage:** {passage.get('title', 'Unknown')}")
    st.text_area("📖 Target Text", value=target_text, height=150, disabled=True)
    st.divider()

    # 2. Record via the browser microphone (no server-side threads needed)
    st.subheader("🎙️ Record the Reading")
    st.caption("Use the microphone to record the student reading aloud, then click Analyze.")
    audio_value = st.audio_input("Record reading", label_visibility="collapsed")

    col1, col2 = st.columns([0.3, 0.7])
    with col1:
        analyze = st.button(
            "✅ Analyze Reading", type="primary",
            disabled=audio_value is None, use_container_width=True,
        )
    with col2:
        if st.button("🔄 Cancel Assessment", use_container_width=True):
            reset_assessment_state()
            st.switch_page("home.py")

    if audio_value is None:
        st.info("Record the reading with the microphone above, then click **Analyze Reading**.")
        return

    if not analyze:
        return

    # 3. Analyze: write WAV → transcribe → align → save
    result, error, tmp_path = None, None, None
    with st.spinner("🔍 Transcribing and analyzing the reading..."):
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(audio_value.getvalue())
                tmp_path = tmp.name
            result = run_assessment_pipeline(tmp_path, target_text)
            record_file = save_record(result, st.session_state["current_passage_id"])
            st.session_state["last_result"] = result
            reset_assessment_state()
        except Exception as e:  # noqa: BLE001 — surface any failure to the user
            error = e
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    # 4. Navigate (kept outside try/except so st.switch_page isn't swallowed)
    if error is not None:
        st.error(f"Analysis failed: {error}")
        st.exception(error)
        return

    st.success(f"✅ Analysis complete! Saved to `{record_file.name}`.")
    st.switch_page("pages/student_results.py")


if __name__ == "__main__":
    main()
