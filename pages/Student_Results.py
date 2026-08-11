import streamlit as st
import pandas as pd

from src.models import AlignmentResult
from src.storage import load_latest_record
from ui import setup_page
from utils import highlight_text, create_error_breakdown_chart, ERROR_LABELS

setup_page("Student Results | Reading Assessment", icon="📊")


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


def main():
    st.title("📊 Student Results")

    result, caption = _load_result()
    if result is None:
        st.info("No results available yet. Please record a reading on the **Student Record** page first.")
        return
    if caption:
        st.caption(caption)

    st.divider()

    # Display Metrics
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

    # Display Text Comparison
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


if __name__ == "__main__":
    main()
