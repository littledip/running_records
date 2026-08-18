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


def assessment_active() -> bool:
    return bool(st.session_state.get("assessment_active", False))


def view_switcher(key: str, options: list[str], default: str | None = None) -> str:
    """Segmented-control tab switcher. `default` only applies on first render —
    once `key` is in session_state (e.g. set programmatically to auto-advance
    to a different view), that value wins."""
    return st.segmented_control(
        "View", options=options, key=key,
        default=default or options[0], required=True,
        label_visibility="collapsed",
    )
