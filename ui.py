"""Shared Streamlit UI helpers used across the multipage app.

Keeps page setup and assessment-state handling consistent in one place (the
`src/` package stays Streamlit-free; this module is the UI-side counterpart).
"""
import streamlit as st

APP_ICON = "📖"

# Session keys that make up an in-progress assessment.
_ASSESSMENT_FLAGS = (
    "assessment_active",
    "recording_in_progress",
    "is_recording",
    "recording_complete",
    "analysis_done",
)


def setup_page(title: str, icon: str = APP_ICON, layout: str = "wide") -> None:
    """Configure the page. Call once, before any other Streamlit command."""
    st.set_page_config(page_title=title, page_icon=icon, layout=layout)


def reset_assessment_state() -> None:
    """Clear all assessment-related session state so no page gets wedged."""
    for key in _ASSESSMENT_FLAGS:
        st.session_state[key] = False
    st.session_state["current_passage_id"] = None
    st.session_state["passage_selection_step"] = 0


def assessment_active() -> bool:
    return bool(st.session_state.get("assessment_active", False))
