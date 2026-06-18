import streamlit as st
import json
from pathlib import Path
from datetime import datetime
import pandas as pd
import uuid

# ───────── Page Setup ─────────
st.set_page_config(page_title="Teacher Dashboard", page_icon="👩‍🏫", layout="wide")
st.title("👩‍🏫 Teacher Dashboard")

# ───────── Paths & Caching ─────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PASSAGES_FILE = PROJECT_ROOT / "passages.json"
RECORDS_DIR = PROJECT_ROOT / "data" / "records"

@st.cache_data(ttl=300)
def load_passages():
    """Load passages manifest. Handles both list and dict JSON formats."""
    if not PASSAGES_FILE.exists():
        return {}
    try:
        with open(PASSAGES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Convert LIST format to DICT format on-the-fly
        if isinstance(data, list):
            # Uses existing "id" field as key, or generates one if missing
            return {item.get("id", f"passage_{i}"): item for i, item in enumerate(data)}
        
        # Already a dict → return as-is
        if isinstance(data, dict):
            return data
            
        st.warning("⚠️ Unexpected JSON structure in passages.json")
        return {}
    except json.JSONDecodeError as e:
        st.error(f"❌ Invalid JSON in passages file: {e}")
        return {}

@st.cache_data(ttl=60)  # Cache records for 1 minute
def load_records():
    """Load all student assessment records."""
    if not RECORDS_DIR.exists():
        return []
    records = []
    for f in sorted(RECORDS_DIR.glob("*.json")):
        try:
            with open(f, "r", encoding="utf-8") as file:
                record = json.load(file)
                record["_file"] = str(f)  # Keep track of source file
                records.append(record)
        except Exception as e:
            st.warning(f"⚠️ Skipped invalid record file: {f.name}")
    return records

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
tab_passages, tab_records, tab_analytics = st.tabs(["📚 Passages", "📊 Student Records", "📈 Analytics"])

# ═══════════════════════════════════════════════════════════
# TAB 1: Passage Management
# ═══════════════════════════════════════════════════════════
with tab_passages:
    st.subheader("Manage Reading Passages")
    st.caption("Edit titles, difficulty levels, and file references. Changes save immediately to `passages.json`.")

    passages = load_passages()
    if not passages:
        st.info("📭 No passages loaded. Add one below or ensure `passages.json` is properly formatted.")

    # Form for adding/editing passages
    with st.form("passage_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            passage_id = st.text_input("Passage ID (e.g., grade2_levelB)", key="new_passage_id")
            title = st.text_input("Title", key="new_title")
        with col2:
            difficulty = st.selectbox("Difficulty Level", ["Level A", "Level B", "Level C", "Level D", "Level E"], key="new_difficulty")
            grade = st.text_input("Grade/Level", key="new_grade")

        submitted = st.form_submit_button("💾 Save Passage", type="primary")

        if submitted:
            if not passage_id or not title:
                st.error("❌ ID and Title are required.")
            else:
                try:
                    with open(PASSAGES_FILE, "r", encoding="utf-8") as f:
                        current_data = json.load(f)
                except (FileNotFoundError, json.JSONDecodeError):
                    current_data = {}

                current_data[passage_id] = {
                    "title": title,
                    "difficulty": difficulty,
                    "grade": grade,
                    "file": f"passages/{passage_id}.txt",  # Auto-generate file ref
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                }

                with open(PASSAGES_FILE, "w", encoding="utf-8") as f:
                    json.dump(current_data, f, indent=2, ensure_ascii=False)

                st.success(f"✅ Passage `{passage_id}` saved successfully.")
                st.rerun()

    # Display current passages as editable table
    if passages:
        df = pd.DataFrame([{k: v.get("title", ""), "difficulty": v.get("difficulty", ""), 
                           "grade": v.get("grade", ""), "file": v.get("file", "")} for k, v in passages.items()])
        
        st.dataframe(df, use_container_width=True)
        
        # Quick delete action
        if st.button("🗑️ Delete Selected Passage(s)", type="secondary"):
            selected = st.session_state.get("passage_selection", [])
            if selected:
                try:
                    with open(PASSAGES_FILE, "r", encoding="utf-8") as f:
                        current_data = json.load(f)
                    for sid in selected:
                        current_data.pop(sid, None)
                    with open(PASSAGES_FILE, "w", encoding="utf-8") as f:
                        json.dump(current_data, f, indent=2, ensure_ascii=False)
                    st.success(f"✅ Deleted {len(selected)} passage(s).")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Failed to delete: {e}")

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
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📊 Total Assessments", len(records))
        with col2:
            st.metric("✅ Avg Accuracy", f"{sum(accuracies)/len(accuracies):.1f}%")
        with col3:
            st.metric("🔍 Avg Miscues", f"{sum(miscues)/len(miscues):.1f}")

        # Chart (if matplotlib/seaborn available)
        try:
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(8, 4))
            ax.plot(accuracies, marker='o', linestyle='-')
            ax.set_title("Accuracy Trend")
            ax.set_xlabel("Assessment #")
            ax.set_ylabel("Accuracy (%)")
            st.pyplot(fig)
        except ImportError:
            st.info("📊 Install `matplotlib` for charts: `pip install matplotlib`")

    # System Status
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
        if st.button("🗑️ Delete records older than 30 days", type="secondary"):
            cutoff = datetime.now().timestamp() - (30 * 24 * 60 * 60)
            deleted = 0
            for f in RECORDS_DIR.glob("*.json"):
                try:
                    with open(f, "r") as file:
                        rec = json.load(file)
                    if datetime.fromisoformat(rec.get("timestamp", "")).timestamp() < cutoff:
                        f.unlink()
                        deleted += 1
                except:
                    pass
            st.success(f"✅ Deleted {deleted} old record(s).")