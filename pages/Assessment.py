import os
import tempfile

import streamlit as st

from src.assessment import run_assessment
from src.config import SHOW_ASSESSMENT_AUDIO_SOURCE_PICKER
from src.karaoke import build_target_word_timings
from src.passages import load_passages
from src.tts import synthesize_speech
from karaoke_ui import render_karaoke_player
from ui import setup_page

setup_page("Assessment | Reading Assessment", icon="🧩")


def _get_audio_with_picker(passage):
    """Manual flow: user chooses to upload a recording or generate TTS via a
    button. Gated behind SHOW_ASSESSMENT_AUDIO_SOURCE_PICKER."""
    source = st.radio("🎵 Audio source", ["Upload a recording", "Generate with text-to-speech"])

    if source == "Upload a recording":
        uploaded = st.file_uploader("Upload audio", type=["wav", "mp3", "m4a", "ogg"])
        if uploaded is not None:
            return uploaded.getvalue(), uploaded.type or "audio/wav"
        return None, "audio/wav"

    if st.button("🔊 Generate audio from passage"):
        with st.spinner("Synthesizing speech..."):
            try:
                st.session_state["assessment_tts_audio"] = synthesize_speech(passage["text"])
                st.session_state["assessment_tts_passage_id"] = passage.get("id")
            except Exception as e:  # noqa: BLE001 — surface any TTS failure to the user
                st.error(f"Text-to-speech failed: {e}")
                st.session_state["assessment_tts_audio"] = None

    if st.session_state.get("assessment_tts_passage_id") == passage.get("id"):
        return st.session_state.get("assessment_tts_audio"), "audio/wav"
    return None, "audio/wav"


def _get_audio_auto_tts(passage):
    """Streamlined flow: TTS is generated automatically for whichever passage
    is selected, no source picker."""
    if st.session_state.get("assessment_tts_passage_id") != passage.get("id"):
        with st.spinner("🔊 Synthesizing speech..."):
            try:
                st.session_state["assessment_tts_audio"] = synthesize_speech(passage["text"])
            except Exception as e:  # noqa: BLE001 — surface any TTS failure to the user
                st.error(f"Text-to-speech failed: {e}")
                st.session_state["assessment_tts_audio"] = None
            st.session_state["assessment_tts_passage_id"] = passage.get("id")

    audio_bytes = st.session_state.get("assessment_tts_audio")
    if audio_bytes is None and st.button("🔄 Retry"):
        st.session_state["assessment_tts_passage_id"] = None
        st.rerun()
    return audio_bytes, "audio/wav"


def main():
    st.title("🧩 Assessment")
    st.caption(
        "Listen to a reading — with the passage highlighted word-by-word as "
        "it plays. Standalone from Running Record; no passage/session setup "
        "needed elsewhere."
    )

    passages = load_passages()
    if not passages:
        st.error("❌ No passages available. Please add passages via the Teacher Dashboard first.")
        return

    passage_options = {f"{p.get('id')} - {p.get('title', 'Untitled')}": p.get("id") for p in passages.values()}
    selected_label = st.selectbox("📖 Select a passage", options=list(passage_options.keys()))
    passage = passages[passage_options[selected_label]]
    target_text = passage.get("text", "")
    st.text_area("Passage text", value=target_text, height=120, disabled=True)

    student_name = st.text_input(
        "👤 Student name",
        key="assessment_student_name_input",
        placeholder="e.g., Jane Doe",
    ).strip()

    st.divider()

    if not student_name:
        st.info("Enter the student's name above to continue.")
        return

    if SHOW_ASSESSMENT_AUDIO_SOURCE_PICKER:
        audio_bytes, audio_mime = _get_audio_with_picker(passage)
        if audio_bytes is None:
            st.info("Provide audio above to generate the read-along player.")
            return
    else:
        audio_bytes, audio_mime = _get_audio_auto_tts(passage)
        if audio_bytes is None:
            return

    st.subheader("🎧 Listen & Follow Along")

    tmp_path = None
    try:
        with st.spinner("🔍 Transcribing and aligning..."):
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name
            result = run_assessment(tmp_path, target_text)
    except Exception as e:  # noqa: BLE001 — surface any failure to the user
        st.error(f"Analysis failed: {e}")
        st.exception(e)
        return
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    timings = build_target_word_timings(result.target_text, result.transcript_text, result.word_segments)
    render_karaoke_player(result.target_text, audio_bytes, audio_mime, timings)

    st.caption("📊 Rubric-based evaluation is planned but not yet implemented here.")


if __name__ == "__main__":
    main()
