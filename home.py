import streamlit as st

from src.config import PASSAGES_FILE
from src.passages import load_passages
from ui import setup_page, reset_assessment_state

setup_page("Reading Assessment | Home")

# ───────── Session State Guards ─────────
if "assessment_active" not in st.session_state:
    st.session_state["assessment_active"] = False
if "recording_in_progress" not in st.session_state:
    st.session_state["recording_in_progress"] = False
if "current_passage_id" not in st.session_state:
    st.session_state["current_passage_id"] = None
if "passage_selection_step" not in st.session_state:
    st.session_state["passage_selection_step"] = 0  # 0=not started, 1=selecting, 2=confirmed

def can_start_assessment():
    """Guard: Prevent duplicate/overlapping assessments."""
    if st.session_state["assessment_active"]:
        st.warning("⚠️ An assessment is already in progress. Complete or cancel it on the Student Record page first.")
        return False
    return True

# ───────── Dashboard UI ─────────
st.title("📖 Automated Reading Assessment")
st.markdown("""
Welcome to the **Running Records** system. This tool uses Whisper speech recognition to evaluate reading accuracy, fluency, and miscues in real time.
""")

# ───────── Step 1: Start Assessment Flow ─────────
col1, col2 = st.columns(2)

with col1:
    if st.button("🎤 Start Student Assessment", type="primary", use_container_width=True):
        if can_start_assessment():
            st.session_state["passage_selection_step"] = 1
            st.rerun()

# ───────── Step 2: Passage Selection (shown when step=1) ─────────
if st.session_state["passage_selection_step"] == 1:
    passages = load_passages()
    
    if not passages:
        st.error("❌ No passages available. Please add passages via the Teacher Dashboard first.")
        if st.button("← Back to Home", use_container_width=True):
            st.session_state["passage_selection_step"] = 0
            st.rerun()
    else:
        passage_options = {f"{p.get('id')} - {p.get('title', 'Untitled')}": p.get("id") for p in passages.values()}
        
        selected_passage_label = st.selectbox(
            "Select a reading passage:",
            options=list(passage_options.keys()),
            key="passage_selector"
        )
        
        if selected_passage_label:
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("✅ Confirm & Start Assessment", type="primary", use_container_width=True):
                    st.session_state["current_passage_id"] = passage_options[selected_passage_label]
                    st.session_state["assessment_active"] = True
                    st.session_state["passage_selection_step"] = 0
                    st.session_state["student_name_input"] = ""  # fresh name for the new assessment
                    st.success(f"✅ Passage assigned: {selected_passage_label}")
                    st.switch_page("pages/student_record.py")
            with col_b:
                if st.button("← Cancel", use_container_width=True):
                    st.session_state["passage_selection_step"] = 0
                    st.rerun()

with col2:
    if st.button("👩‍🏫 Teacher Dashboard", use_container_width=True):
        st.switch_page("pages/teacher_admin.py")

# ───────── System Status ─────────
st.subheader("🔧 System Status")
if PASSAGES_FILE.exists():
    st.success("✅ Passages manifest loaded successfully")
else:
    st.error("❌ Passages file missing. Ensure `passages.json` is in the project root.")

# ───────── Optional State Reset ─────────
with st.expander("🔧 Advanced: Reset Assessment State"):
    if st.button("Clear all assessment state", type="secondary"):
        reset_assessment_state()
        st.success("✅ Assessment state cleared. You can start a new recording.")
