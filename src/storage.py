"""Assessment-record repository — persistence for completed assessments.

Replaces the inline JSON read/write that lived in Student_Record.py (write) and
Teacher_Dashboard.py (read). Records are one JSON file per assessment under
config.RECORDS_DIR. No Streamlit imports.
"""
import json
import time
from pathlib import Path

from .config import RECORDS_DIR, ensure_records_dir


def save_record(record: dict, records_dir: Path = RECORDS_DIR) -> Path:
    """Write a record dict to <records_dir>/<student_id>_<timestamp>.json."""
    ensure_records_dir() if records_dir is RECORDS_DIR else records_dir.mkdir(parents=True, exist_ok=True)
    student_id = record.get("student_id", "Unknown")
    filename = f"{student_id}_{time.strftime('%Y%m%d_%H%M%S')}.json"
    path = records_dir / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
    return path


def list_records(records_dir: Path = RECORDS_DIR) -> list[dict]:
    """Return all records (each annotated with its source path under '_file'),
    sorted by filename. Invalid files are skipped."""
    if not records_dir.exists():
        return []
    records = []
    for f in sorted(records_dir.glob("*.json")):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                record = json.load(fh)
            record["_file"] = str(f)
            records.append(record)
        except (json.JSONDecodeError, OSError):
            continue
    return records


def load_latest_record(records_dir: Path = RECORDS_DIR) -> dict | None:
    """Return the most recent record by its 'timestamp' field, or None.

    Note: we sort by the timestamp field rather than filename, because filenames
    are prefixed with student_id (so filename order is alphabetical by student,
    not chronological).
    """
    records = list_records(records_dir)
    if not records:
        return None
    return max(records, key=lambda r: r.get("timestamp", ""))
