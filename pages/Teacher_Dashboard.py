import streamlit as st
from datetime import datetime
import pandas as pd

from src.config import PASSAGES_FILE, RECORDS_DIR
from src import passages as passages_lib
from src.storage import count_records_older_than, delete_records_older_than, list_records
from ui import setup_page

# ───────── Page Setup ─────────
setup_page("Teacher Dashboard | Reading Assessment", icon="👩‍🏫")
st.title("👩‍🏫 Teacher Dashboard")


# ───────── Cached views over the core (cleared on writes) ─────────
@st.cache_data(ttl=300)
def load_passages():
    return passages_lib.load_passages()


@st.cache_data(ttl=60)
def load_records():
    return list_records()

# ───────── Session State Guards ─────────
if "assessment_active" not in st.session_state:
    st.session_state["assessment_active"] = False

def guard_teacher_access():
    if st.session_state.get("assessment_active", False):
        # Check if assessment is genuinely active (still recording) or stuck
        if st.session_state.get("is_recording", False):
            # Genuinely active — user is mid-recording
            st.warning("⚠️ A student assessment is currently active. Please complete it before accessing admin tools.")
        else:
            # Assessment flag is set but not recording → stuck/stale state
            st.warning("⚠️ Assessment appears to be stuck. Click below to reset.")
            if st.button("🔄 Reset Assessment State", type="primary"):
                st.session_state["assessment_active"] = False
                st.rerun()
        return False
    return True

if not guard_teacher_access():
    st.stop()

# ───────── Tab Navigation ─────────
tab_passages, tab_records, tab_analytics, tab_system = st.tabs(
    ["📚 Passages", "📊 Student Records", "📈 Analytics", "🔧 System Status"]
)

# ═══════════════════════════════════════════════════════════
# TAB 1: Passage Management
# ═══════════════════════════════════════════════════════════
with tab_passages:
    st.subheader("Manage Reading Passages")
    st.caption("Create, edit, and delete passages. Changes save immediately to `passages.json`.")

    passages = load_passages()
    if not passages:
        st.info("📭 No passages loaded. Add one below or ensure `passages.json` is properly formatted.")

    NEW_PASSAGE_LABEL = "➕ Create new passage"

    # Apply a pending selector/form reset (set after a successful save, below)
    # before the widgets render — can't set a widget's own session-state key
    # after it's already rendered this run. Handled explicitly here rather
    # than via st.form(clear_on_submit=True): that combined with our own
    # programmatic pre-fill below caused the form to keep reverting to blank
    # on every later rerun, not just the one right after a submit.
    if "_pending_passage_edit_choice" in st.session_state:
        st.session_state["passage_edit_choice"] = st.session_state.pop("_pending_passage_edit_choice")
    if st.session_state.pop("_pending_passage_form_reset", False):
        st.session_state["new_passage_id"] = ""
        st.session_state["new_title"] = ""
        st.session_state["new_difficulty"] = "Level A"
        st.session_state["new_grade"] = ""
        st.session_state["new_text"] = ""
        st.session_state["_passage_form_loaded_id"] = None

    label_to_id = {NEW_PASSAGE_LABEL: None}
    for pid, p in passages.items():
        label_to_id[f"{pid} - {p.get('title', 'Untitled')}"] = pid

    edit_choice = st.selectbox(
        "Select a passage to edit, or create a new one",
        options=list(label_to_id.keys()), key="passage_edit_choice",
    )
    editing_id = label_to_id[edit_choice]
    editing_passage = passages.get(editing_id) if editing_id is not None else None

    # Pre-fill the form when the edit target changes — guarded so it only
    # fires once per selection (not on every rerun, which would stomp on
    # in-progress edits to the text fields below).
    if st.session_state.get("_passage_form_loaded_id") != editing_id:
        st.session_state["new_passage_id"] = str(editing_id) if editing_id is not None else ""
        st.session_state["new_title"] = (editing_passage or {}).get("title", "")
        st.session_state["new_difficulty"] = (editing_passage or {}).get("difficulty", "Level A")
        st.session_state["new_grade"] = (editing_passage or {}).get("grade", "")
        st.session_state["new_text"] = (editing_passage or {}).get("text", "")
        st.session_state["_passage_form_loaded_id"] = editing_id

    # Plain (non-form) widgets — deliberately not st.form(): a form's inputs
    # don't rerun the script until submitted, so a Save button whose
    # `disabled` depends on "has anything changed" needs every keystroke to
    # rerun and re-evaluate that live.
    col1, col2 = st.columns(2)
    with col1:
        passage_id = st.text_input(
            "Passage ID (e.g., grade2_levelB)", key="new_passage_id",
            disabled=editing_passage is not None,
        )
        title = st.text_input("Title", key="new_title")
    with col2:
        difficulty = st.selectbox("Difficulty Level", ["Level A", "Level B", "Level C", "Level D", "Level E"], key="new_difficulty")
        grade = st.text_input("Grade/Level", key="new_grade")

    text = st.text_area("Passage Text", key="new_text", height=150)

    # While editing, disable Save until a field actually differs from the
    # loaded passage — avoids no-op re-saves that just bump updated_at.
    unchanged = editing_passage is not None and (
        title == editing_passage.get("title", "")
        and difficulty == editing_passage.get("difficulty", "Level A")
        and grade == editing_passage.get("grade", "")
        and text == editing_passage.get("text", "")
    )

    submit_label = "💾 Save Changes" if editing_passage is not None else "💾 Save Passage"
    if st.button(submit_label, type="primary", disabled=unchanged):
        if not passage_id or not title or not text:
            st.error("❌ ID, Title, and Passage Text are required.")
        else:
            # When editing, use the original id (may be an int, e.g. from
            # passages.json) rather than the disabled text_input's string
            # value, so the upsert in save_passage() matches by the same
            # type and replaces the row instead of creating a duplicate.
            save_id = editing_id if editing_passage is not None else passage_id
            passages_lib.save_passage({
                "id": save_id,
                "title": title,
                "difficulty": difficulty,
                "grade": grade,
                "text": text,
                "created_at": (editing_passage or {}).get("created_at", datetime.now().isoformat()),
                "updated_at": datetime.now().isoformat(),
            })
            load_passages.clear()  # invalidate cache so the edit shows immediately
            st.session_state["_pending_passage_edit_choice"] = NEW_PASSAGE_LABEL
            st.session_state["_pending_passage_form_reset"] = True
            st.success(f"✅ Passage `{save_id}` saved successfully.")
            st.rerun()

    # Display current passages with row-selection delete
    if passages:
        rows = [
            {"ID": pid, "Title": p.get("title", ""),
             "Difficulty": p.get("difficulty", ""), "Grade": p.get("grade", ""),
             "Text": (p.get("text", "")[:60] + "…") if len(p.get("text", "")) > 60 else p.get("text", "")}
            for pid, p in passages.items()
        ]
        st.caption("Select one or more rows to delete.")
        event = st.dataframe(
            pd.DataFrame(rows), use_container_width=True, hide_index=True,
            on_select="rerun", selection_mode="multi-row",
        )
        selected_ids = [rows[i]["ID"] for i in event.selection.rows]

        if st.button("🗑️ Delete Selected Passage(s)", type="secondary",
                     disabled=not selected_ids):
            removed = passages_lib.delete_passages(selected_ids)
            load_passages.clear()  # invalidate cache so the change shows immediately
            st.success(f"✅ Deleted {removed} passage(s).")
            st.rerun()

# ═══════════════════════════════════════════════════════════
# TAB 2: Student Records Viewer
# ═══════════════════════════════════════════════════════════
with tab_records:
    st.subheader("Student Assessment Records")
    st.caption("View, filter, and export reading assessments. Files are stored in `data/records/`.")

    records = load_records()
    
    if not records:
        st.info("📭 No assessment records found yet. Complete a student recording on the Student Record page to generate data.")
    else:
        # Filters
        col1, col2, col3 = st.columns(3)
        with col1:
            search_term = st.text_input("🔍 Search by student name or ID", placeholder="e.g., John Doe")
        with col2:
            date_filter = st.date_input("📅 Filter by date", value=None)
        with col3:
            sort_by = st.selectbox("📊 Sort by", ["Date (Newest)", "Date (Oldest)", "Accuracy (%)", "Miscues"])

        # Apply filters
        filtered = records.copy()
        if search_term:
            filtered = [r for r in filtered if search_term.lower() in str(r.get("student_name", "")).lower() or 
                        search_term.lower() in str(r.get("student_id", "")).lower()]
        
        if date_filter:
            filtered = [r for r in filtered if datetime.fromisoformat(r.get("timestamp", "")[:10]).date() == date_filter]

        # Sort
        if sort_by == "Date (Newest)":
            filtered.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        elif sort_by == "Date (Oldest)":
            filtered.sort(key=lambda x: x.get("timestamp", ""))
        elif sort_by in ["Accuracy (%)", "Miscues"]:
            filtered.sort(key=lambda x: float(x.get(sort_by.replace(" ", "").replace("%", ""), 0)), reverse=True)

        # Display table
        if filtered:
            display_df = pd.DataFrame([{
                "Student": r.get("student_name", "N/A"),
                "ID": r.get("student_id", "N/A"),
                "Date": datetime.fromisoformat(r.get("timestamp", "")).strftime("%Y-%m-%d %H:%M") if "timestamp" in r else "N/A",
                "Passage": r.get("passage_id", "N/A"),
                "Accuracy (%)": f"{float(r.get('accuracy_pct', 0)):.1f}",
                "Miscues": r.get("miscue_count", 0),
                "WER": f"{float(r.get('word_error_rate', 0)):.2f}"
            } for r in filtered])

            st.dataframe(display_df, use_container_width=True)

            # Export button
            if st.button("📥 Export Filtered Records to CSV", type="primary"):
                csv = display_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="⬇️ Download CSV",
                    data=csv,
                    file_name=f"assessments_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv"
                )

            # Detail view (expandable)
            for i, rec in enumerate(filtered):
                with st.expander(f"📄 {rec.get('student_name', 'Unknown')} - {rec.get('passage_id', 'N/A')}"):
                    st.json(rec)

        else:
            st.warning("⚠️ No records match your filters.")

# ═══════════════════════════════════════════════════════════
# TAB 3: Analytics & System Status
# ═══════════════════════════════════════════════════════════
with tab_analytics:
    st.subheader("📈 Assessment Analytics")
    
    if not records:
        st.info("📊 Analytics will populate once student assessments are completed.")
    else:
        # Basic metrics
        accuracies = [float(r.get("accuracy_pct", 0)) for r in records]
        miscues = [int(r.get("miscue_count", 0)) for r in records]
        
        col1, col2, col3, _ = st.columns([1.6, 1.3, 1.3, 2.8])
        with col1:
            st.metric("📊 Total Assessments", len(records))
        with col2:
            st.metric("✅ Avg Accuracy", f"{sum(accuracies)/len(accuracies):.1f}%")
        with col3:
            st.metric("🔍 Avg Miscues", f"{sum(miscues)/len(miscues):.1f}")

        # Chart (if matplotlib/seaborn available) — kept in a narrow column so
        # it doesn't stretch full-width; leaves room alongside it for other
        # metrics later.
        try:
            import matplotlib.pyplot as plt
            chart_col, _ = st.columns([2, 3])
            with chart_col:
                fig, ax = plt.subplots(figsize=(5, 2.2))
                ax.plot(accuracies, marker='o', linestyle='-')
                ax.set_title("Accuracy Trend", fontsize=10)
                ax.set_xlabel("Assessment #", fontsize=8)
                ax.set_ylabel("Accuracy (%)", fontsize=8)
                ax.tick_params(labelsize=7)
                fig.tight_layout()
                st.pyplot(fig)
        except ImportError:
            st.info("📊 Install `matplotlib` for charts: `pip install matplotlib`")

# ═══════════════════════════════════════════════════════════
# TAB 4: System Status
# ═══════════════════════════════════════════════════════════
with tab_system:
    st.subheader("🔧 System Status")
    col1, col2 = st.columns(2)
    with col1:
        if PASSAGES_FILE.exists():
            st.success(f"✅ Passages file loaded ({len(load_passages())} passages)")
        else:
            st.error("❌ Passages file missing")

        if RECORDS_DIR.exists():
            rec_count = len(list(RECORDS_DIR.glob("*.json")))
            st.info(f"📁 Records directory: {rec_count} files found")
        else:
            st.warning("⚠️ Records directory not found. Create `data/records/` to store assessments.")

    with col2:
        st.caption("💡 Tip: Whisper transcription results should be saved as JSON files in `data/records/` with keys like:")
        st.code("""{
  "student_id": "S001",
  "student_name": "Jane Doe",
  "passage_id": "grade2_levelB",
  "timestamp": "2024-06-15T14:30:00",
  "accuracy_pct": 92.5,
  "miscue_count": 2,
  "word_error_rate": 0.075,
  "transcript": "...",
  "audio_file": "..."
}""")

    # Cleanup old records (optional)
    with st.expander("🧹 Maintenance: Clean Old Records"):
        days = st.radio(
            "Delete records older than:",
            options=[15, 30, 60],
            format_func=lambda d: f"{d} days",
            horizontal=True,
        )
        stale_count = count_records_older_than(days)
        st.caption(f"{stale_count} record(s) older than {days} days.")
        if st.button(f"🗑️ Delete {stale_count} record(s)", type="secondary", disabled=stale_count == 0):
            deleted = delete_records_older_than(days)
            load_records.clear()  # invalidate the cached records list
            st.success(f"✅ Deleted {deleted} old record(s).")
            st.rerun()