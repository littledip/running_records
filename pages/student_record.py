import streamlit as st
import tempfile
import os

from src.assessment import run_assessment, result_to_record
from src.passages import get_passage
from src.storage import save_record
from ui import setup_page, reset_assessment_state

setup_page("Student Record | Reading Assessment", icon="🎤")

# ───────── Session State & Guards ─────────
if "assessment_active" not in st.session_state:
    st.session_state["assessment_active"] = False


def guard_assessment():
    if not st.session_state.get("assessment_active", False):
        st.warning("🚫 Please start a new assessment from the Home page first.")
        return False
    return True


if not guard_assessment():
    st.stop()  # Prevents recording/analysis logic from running if guard fails


def main():
    st.title("🎤 Student Record")

    # 1. Resolve the assigned passage
    passage_id = st.session_state.get("current_passage_id")
    if not passage_id:
        st.warning("No passage assigned. Please start an assessment from the Home page.")
        return

    passage = get_passage(passage_id)
    if not passage:
        st.error(f"Assigned passage '{passage_id}' not found.")
        return

    target_text = passage.get("text", "")
    st.markdown(f"**Reading Passage:** {passage.get('title', 'Unknown')}")
    st.text_area("📖 Target Text", value=target_text, height=150, disabled=True)

    # Student identity — so saved records aren't all "Unknown"
    student_name = st.text_input(
        "👤 Student name",
        value=st.session_state.get("current_student_name", ""),
        placeholder="e.g., Jane Doe",
    ).strip()
    st.session_state["current_student_name"] = student_name
    st.session_state["current_student_id"] = student_name.replace(" ", "_") or "Unknown"

    st.divider()

    # 2. Record via the browser microphone (no server-side threads needed)
    st.subheader("🎙️ Record the Reading")
    st.caption("Use the microphone to record the student reading aloud, then click Analyze.")
    audio_value = st.audio_input("Record reading", label_visibility="collapsed")

    col1, col2 = st.columns([0.3, 0.7])
    with col1:
        analyze = st.button(
            "✅ Analyze Reading", type="primary",
            disabled=audio_value is None or not student_name, use_container_width=True,
        )
    with col2:
        if st.button("🔄 Cancel Assessment", use_container_width=True):
            reset_assessment_state()
            st.switch_page("home.py")

    if not student_name:
        st.info("Enter the student's name above to begin.")
        return

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
            result = run_assessment(tmp_path, target_text)
            record = result_to_record(
                result, passage_id,
                student_id=st.session_state.get("current_student_id", "Unknown"),
                student_name=st.session_state.get("current_student_name"),
            )
            record_file = save_record(record)
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
