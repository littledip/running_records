import html
import os
import tempfile

import pandas as pd
import streamlit as st

from src.assessment import run_assessment, result_to_record
from src.models import AlignmentResult
from src.passages import get_passage, load_passages
from src.storage import load_latest_record, save_record
from ui import reset_assessment_state, setup_page, step_gate, view_switcher
from utils import ERROR_LABELS, create_error_breakdown_chart, highlight_text

setup_page("Reading Assessment | Running Record")

VIEW_KEY = "running_record_view"
RECORD_VIEW = "Student Record"
RESULTS_VIEW = "Student Results"


def _label_text(text: str) -> None:
    """Render text at the same color/size/weight as a widget label (e.g.
    "Student name"). st.caption renders identical base CSS but its container
    applies opacity:0.6, which is why captions look lighter/dimmer."""
    st.markdown(
        f'<p style="font-size:14px; font-weight:400; margin-bottom:0.25rem;">{text}</p>',
        unsafe_allow_html=True,
    )


def _student_record_view():
    st.subheader("🎤 Student Record")

    # Apply a pending name reset (set by "Start Over", below) before the
    # text_input renders — can't set a widget's own session-state key after
    # it's already rendered this run.
    if st.session_state.pop("_pending_rr_name_reset", False):
        st.session_state["student_name_input"] = ""

    student_name = st.text_input(
        "👤 Student name",
        key="student_name_input",
        placeholder="e.g., Jane Doe",
    ).strip()

    def _reset_after_name_cleared():
        st.session_state["rr_passage_selector"] = None
        st.session_state["rr_attempt"] = st.session_state.get("rr_attempt", 0) + 1
        reset_assessment_state()

    if not step_gate(
        "rr_name", student_name, reset_fn=_reset_after_name_cleared,
        prompt="Enter the student's name above to continue.",
    ):
        return

    st.session_state["current_student_name"] = student_name
    st.session_state["current_student_id"] = student_name.replace(" ", "_") or "Unknown"

    passages = load_passages()
    if not passages:
        st.error("❌ No passages available. Please add passages via the Teacher Dashboard first.")
        return

    passage_options = {f"{p.get('id')} - {p.get('title', 'Untitled')}": p.get("id") for p in passages.values()}
    selected_label = st.selectbox(
        "📖 Select a reading passage", options=list(passage_options.keys()), key="rr_passage_selector",
        index=None, placeholder="Choose a passage...",
    )

    def _reset_after_passage_cleared():
        st.session_state["rr_attempt"] = st.session_state.get("rr_attempt", 0) + 1
        reset_assessment_state()

    if not step_gate(
        "rr_passage", selected_label, reset_fn=_reset_after_passage_cleared,
        prompt="Select a reading passage above to reveal recording.",
    ):
        return

    passage_id = passage_options[selected_label]
    st.session_state["current_passage_id"] = passage_id
    passage = get_passage(passage_id)
    target_text = passage.get("text", "")

    _label_text("📖 Target Text")
    TEXT_SIZES = {"Small": "14px", "Medium": "18px", "Large": "22px"}
    col_a, col_b, _ = st.columns([1, 2, 4], gap="small")
    with col_a:
        _label_text("Dark background")
        dark_background = st.toggle(
            "Dark background", value=True, key="rr_target_dark_mode", label_visibility="collapsed"
        )
    with col_b:
        _label_text("Text size")
        size_label = st.segmented_control(
            "Text size", options=list(TEXT_SIZES.keys()), default="Medium",
            key="rr_target_text_size", required=True, label_visibility="collapsed",
        )
    font_size = TEXT_SIZES.get(size_label, TEXT_SIZES["Medium"])

    bg, fg = ("#000000", "#ffffff") if dark_background else ("#ffffff", "#000000")
    border = "none" if dark_background else "1px solid #d0d0d0"
    st.markdown(
        f'<div style="background-color:{bg}; color:{fg}; padding:12px 14px; '
        f'border-radius:6px; border:{border}; min-height:150px; white-space:pre-wrap; '
        f'font-size:{font_size}; line-height:1.5; margin-bottom:20px;">{html.escape(target_text)}</div>',
        unsafe_allow_html=True,
    )

    st.session_state["assessment_active"] = True

    _label_text("Click the microphone below to record the reading of the passage, and then click Analyze Reading.")
    attempt = st.session_state.get("rr_attempt", 0)
    audio_value = st.audio_input("Record reading", key=f"rr_audio_{attempt}", label_visibility="collapsed")

    col1, col2 = st.columns([0.3, 0.7])
    with col1:
        analyze = st.button(
            "✅ Analyze Reading", type="primary",
            disabled=audio_value is None, use_container_width=True,
        )
    with col2:
        if st.button("🔄 Start Over", use_container_width=True):
            # Just clear the name and rerun — step_gate's own reset_fn (above)
            # detects the transition to empty and reinitializes everything
            # downstream (passage selection, recording attempt, etc.).
            st.session_state["_pending_rr_name_reset"] = True
            st.rerun()

    if audio_value is None:
        return

    if not analyze:
        return

    result, error, tmp_path = None, None, None
    record_file = None
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
            st.session_state["assessment_active"] = False
        except Exception as e:  # noqa: BLE001 — surface any failure to the user
            error = e
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    if error is not None:
        st.error(f"Analysis failed: {error}")
        st.exception(error)
        return

    st.success(f"✅ Analysis complete! Saved to `{record_file.name}`.")
    # Can't set st.session_state[VIEW_KEY] directly here — the switcher widget
    # (key=VIEW_KEY) already rendered earlier this run, in main(). Stash the
    # target view and apply it before the widget renders on the next run.
    st.session_state["_pending_view"] = RESULTS_VIEW
    st.rerun()


def _load_result():
    """Return (result, caption). Prefer the in-session result; fall back to the
    latest saved record so results survive a page refresh."""
    result = st.session_state.get("last_result")
    if result is not None:
        return result, None

    record = load_latest_record()
    if record and record.get("alignment"):
        try:
            restored = AlignmentResult.model_validate(record["alignment"])
        except Exception:
            return None, None
        name = record.get("student_name", "Unknown")
        return restored, f"Showing the most recent saved result for **{name}**."
    return None, None


def _student_results_view():
    st.subheader("📊 Student Results")

    result, caption = _load_result()
    if result is None:
        st.info("No results available yet. Switch to **Student Record** to record a reading first.")
        return
    if caption:
        st.caption(caption)

    st.divider()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Accuracy", f"{result.metrics.accuracy:.0%}")
    with col2:
        st.metric("Words per Minute", f"{result.metrics.wpm:.1f}")
    with col3:
        st.metric("Total Words", result.metrics.total_words)
    with col4:
        st.metric("Errors Detected", result.metrics.error_count)

    st.divider()

    transcript_text = getattr(result, "transcript_text", "") or ""
    highlighted = highlight_text(result.target_text, transcript_text, result.errors)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Target Text:**", unsafe_allow_html=True)
        st.markdown(highlighted["target_html"], unsafe_allow_html=True)
    with c2:
        st.markdown("**Your Transcript:**", unsafe_allow_html=True)
        st.markdown(highlighted["transcript_html"], unsafe_allow_html=True)

    if result.errors:
        st.divider()
        st.subheader("🔍 Error Breakdown")
        chart = create_error_breakdown_chart(result.errors)
        if chart:
            st.altair_chart(chart, use_container_width=True)

        st.subheader("❌ Detailed Errors")
        error_df = pd.DataFrame([
            {
                "Type": ERROR_LABELS.get(e.error_type, e.error_type),
                "Target Word": e.target_word or "-",
                "Confidence": f"{e.confidence:.0%}" if hasattr(e, "confidence") else "-",
                "Reason": e.reason,
            }
            for e in result.errors
        ])
        st.dataframe(error_df, use_container_width=True, hide_index=True)


def main():
    st.title("📖 Running Record")
    st.caption(
        "Record a student reading aloud and review Whisper-scored accuracy, "
        "fluency, and miscues."
    )

    if "_pending_view" in st.session_state:
        st.session_state[VIEW_KEY] = st.session_state.pop("_pending_view")

    view = view_switcher(VIEW_KEY, options=[RECORD_VIEW, RESULTS_VIEW])
    if view == RECORD_VIEW:
        _student_record_view()
    else:
        _student_results_view()


if __name__ == "__main__":
    main()
