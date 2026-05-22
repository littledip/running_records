"""Streamlit Dashboard for Running Record Analysis.

Usage:
    cd /Users/johnd/projects/running_records
    source app_env/bin/activate
    streamlit run streamlit_app.py

Features:
- Upload audio file (.wav) or use demo mode with sample data
- Visualize transcription vs target text with error highlighting
- Display accuracy, WPM, and reading rate metrics
- Breakdown errors by type (substitution, omission, insertion, word_order)
"""

import sys
from pathlib import Path
from typing import List, Dict, Any

import streamlit as st
import pandas as pd
import altair as alt
from PIL import Image
import io

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.pipeline import WhisperASRService
from src.alignment import AlignmentEngine
from src.models import (
    RunningRecordResult,
    AlignmentResult,
    ErrorType,
    AlignmentMetrics,
)


# ─── Constants ────────────────────────────────────────────────────────────────

ERROR_COLORS = {
    "substitution": "#ff6b6b",  # Red
    "omission": "#ffa502",      # Orange
    "insertion": "#7bed9f",     # Green
    "word_order": "#70a1ff",    # Blue
    "self_correction": "#a4b0be", # Grey
}

ERROR_LABELS = {
    "substitution": "Substitution",
    "omission": "Omission",
    "insertion": "Insertion",
    "word_order": "Word Order",
    "self_correction": "Self-Correction",
}


# ─── Helper Functions ────────────────────────────────────────────────────────

def highlight_text(
    target_text: str,
    transcript_text: str,
    errors: List[ErrorType],
) -> Dict[str, Any]:
    """Generate highlighted HTML for target and transcript text.

    Returns dict with 'target_html' and 'transcript_html' keys.
    """
    # Build error spans for each error type
    target_spans = _build_error_spans(target_text, errors, "target")
    transcript_spans = _build_error_spans(transcript_text, errors, "transcript")

    return {
        "target_html": target_spans["html"],
        "transcript_html": transcript_spans["html"],
    }


def _build_error_spans(text: str, errors: List[ErrorType], mode: str) -> Dict[str, Any]:
    """Build HTML spans with error highlighting for a given text."""
    words = text.split()
    if not words:
        return {"html": text, "word_count": 0}

    # Map each word to its errors (by position)
    word_errors: Dict[int, List[ErrorType]] = {}
    for err in errors:
        if err.target_word:
            target_words = [w.lower() for w in err.target_word.split()]
            transcript_words = [w.lower() for w in text.split()]
            # Find positions where this error applies
            for i, word in enumerate(transcript_words):
                if word in target_words or any(word == tw for tw in target_words):
                    if i not in word_errors:
                        word_errors[i] = []
                    word_errors[i].append(err)

    # Build HTML with colored spans
    highlighted_words = []
    for i, word in enumerate(words):
        if i in word_errors:
            error_types = [e.error_type for e in word_errors[i]]
            color = ERROR_COLORS.get(error_types[0], "#dfe4ea")
            label = " | ".join(ERROR_LABELS.get(et, et) for et in error_types)
            highlighted_words.append(
                f'<span style="background-color: {color}; padding: 2px 4px; '
                f'border-radius: 3px; margin: 1px; display: inline-block;" '
                f'title="{label}">{word}</span>'
            )
        else:
            highlighted_words.append(word)

    return {"html": " ".join(highlighted_words), "word_count": len(words)}


def create_error_breakdown_chart(errors: List[ErrorType]):
    """Create a bar chart showing error counts by type."""
    if not errors:
        return None

    # Count errors by type
    error_counts = {}
    for err in errors:
        error_counts[err.error_type] = error_counts.get(err.error_type, 0) + 1

    # Create DataFrame
    df = pd.DataFrame([
        {"Error Type": ERROR_LABELS.get(et, et), "Count": count}
        for et, count in error_counts.items()
    ])

    # Create chart
    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("Error Type", sort=list(ERROR_LABELS.values()), title=""),
            y=alt.Y("Count", title="Number of Errors"),
            color=alt.Color(
                "Error Type",
                scale=alt.Scale(
                    domain=list(ERROR_LABELS.keys()),
                    range=list(ERROR_COLORS.values()),
                ),
                legend=None,
            ),
            tooltip=["Error Type", "Count"],
        )
        .properties(
            width=300,
            height=200,
        )
    )

    return chart


def create_accuracy_gauge(metrics: AlignmentMetrics) -> Dict[str, Any]:
    """Create accuracy visualization data."""
    return {
        "accuracy": metrics.accuracy,
        "wpm": metrics.wpm,
        "total_words": metrics.total_words,
        "error_count": metrics.error_count,
    }


def load_demo_data() -> AlignmentResult:
    """Return demo alignment result for testing without audio."""
    target_text = "How much wood could a woodchuck chuck if a woodchuck could chuck wood?"
    transcript_text = "How much chuck could a chuck would would if a chuck would could would chuck?"

    errors = [
        ErrorType(error_type="substitution", confidence=0.92, reason="Phonetic mismatch"),
        ErrorType(error_type="substitution", confidence=0.92, reason="Phonetic mismatch"),
        ErrorType(error_type="insertion", confidence=0.95, reason="Extra word 'wood' not in target text"),
        ErrorType(error_type="insertion", confidence=0.95, reason="Extra word 'chuck' not in target text"),
        ErrorType(error_type="substitution", confidence=0.92, reason="Phonetic mismatch"),
        ErrorType(error_type="word_order", confidence=0.85, reason="Word 'if' appears at position 7 in target but 8 in transcript"),
        ErrorType(error_type="word_order", confidence=0.85, reason="Word 'a' appears at position 8 in target but 9 in transcript"),
        ErrorType(error_type="word_order", confidence=0.85, reason="Word 'wood' appears at position 2 in target but 5 in transcript"),
        ErrorType(error_type="word_order", confidence=0.85, reason="Word 'chuck' appears at position 6 in target but 2 in transcript"),
        ErrorType(error_type="word_order", confidence=0.85, reason="Word 'chuck' appears at position 11 in target but 6 in transcript"),
    ]

    metrics = AlignmentMetrics(
        accuracy=0.6,
        wpm=63.6,
        reading_rate_variance=0.0,
        total_words=15,
        error_count=6,
    )

    return AlignmentResult(
        target_text=target_text,
        transcript_text=transcript_text,
        word_segments=[],
        errors=errors,
        metrics=metrics,
    )


# ─── Streamlit App ──────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="Running Record Analyzer",
        page_icon="📖",
        layout="wide",
    )

    st.title("📖 Running Record Analyzer")
    st.caption("Upload an audio file or use demo mode to analyze reading errors.")

    # Sidebar controls
    with st.sidebar:
        st.header("Configuration")
        mode = st.radio(
            "Mode",
            ["Demo Mode", "Upload Audio"],
            help="Demo mode uses sample data. Upload audio for real analysis.",
        )

        if mode == "Demo Mode":
            st.info("Uses pre-built sample data with known errors.")
            result = load_demo_data()
        else:
            uploaded_file = st.file_uploader(
                "Upload .wav audio file",
                type=["wav"],
                help="Upload a WAV recording of someone reading the target text.",
            )

            if uploaded_file is None:
                st.warning("Please upload a .wav file to proceed.")
                return

            # Target text input
            target_text = st.text_area(
                "Target Text (what the child should read)",
                value="The rain in Spain falls mainly in the plain.",
                help="Enter the passage the child was asked to read.",
            )

            if not target_text.strip():
                st.warning("Please enter a target text.")
                return

            # Process audio
            with st.spinner("Transcribing and analyzing..."):
                try:
                    # Save uploaded file temporarily
                    import tempfile
                    tmp_path = tempfile.mktemp(suffix=".wav")
                    with open(tmp_path, "wb") as f:
                        f.write(uploaded_file.read())

                    # Run ASR pipeline
                    asr_service = WhisperASRService()
                    record_result = asr_service.transcribe_file(tmp_path)
                    record_result.target_text = target_text

                    # Run alignment
                    engine = AlignmentEngine()
                    result = engine.process_result(record_result)

                    import os
                    os.unlink(tmp_path)
                except Exception as e:
                    st.error(f"Analysis failed: {e}")
                    return

    # Display results
    if result:
        # Metrics cards
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

        # Text comparison
        st.subheader("📝 Text Comparison")
        highlighted = highlight_text(result.target_text, result.transcript_text, result.errors)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Target Text:**", unsafe_allow_html=True)
            st.markdown(highlighted["target_html"], unsafe_allow_html=True)
        with col2:
            st.markdown("**Transcript:**", unsafe_allow_html=True)
            st.markdown(highlighted["transcript_html"], unsafe_allow_html=True)

        st.divider()

        # Error breakdown chart
        if result.errors:
            st.subheader("🔍 Error Breakdown")
            chart = create_error_breakdown_chart(result.errors)
            if chart:
                st.altair_chart(chart, use_container_width=True)

        # Detailed errors table
        if result.errors:
            st.subheader("❌ Detailed Errors")
            error_df = pd.DataFrame([
                {
                    "Type": ERROR_LABELS.get(e.error_type, e.error_type),
                    "Target Word": e.target_word or "-",
                    "Confidence": f"{e.confidence:.0%}",
                    "Reason": e.reason,
                }
                for e in result.errors
            ])

            st.dataframe(
                error_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Type": st.column_config.Column(
                        "Error Type",
                        width="medium",
                    ),
                    "Target Word": st.column_config.Column(
                        "Target Word",
                        width="small",
                    ),
                    "Confidence": st.column_config.NumberColumn(
                        "Confidence",
                        format="%.2f",
                        width="small",
                    ),
                    "Reason": st.column_config.Column(
                        "Details",
                        width="large",
                    ),
                },
            )


if __name__ == "__main__":
    main()
