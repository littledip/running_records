"""Tests for the assessment-record repository (src/storage.py)."""
import time
from datetime import datetime

from src import storage


def _timestamp_days_ago(days: float) -> str:
    return datetime.fromtimestamp(time.time() - days * 86400).isoformat()


def test_save_and_list_records(tmp_path):
    path = storage.save_record({"student_id": "S1", "accuracy_pct": 90.0}, tmp_path)
    assert path.exists()
    records = storage.list_records(tmp_path)
    assert len(records) == 1
    assert records[0]["student_id"] == "S1"
    assert records[0]["_file"] == str(path)


def test_list_records_missing_dir(tmp_path):
    assert storage.list_records(tmp_path / "nope") == []


def test_list_records_skips_invalid(tmp_path):
    (tmp_path / "good.json").write_text('{"student_id": "S"}', encoding="utf-8")
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    records = storage.list_records(tmp_path)
    assert len(records) == 1
    assert records[0]["student_id"] == "S"


def test_load_latest_record_uses_timestamp_not_filename(tmp_path):
    # "Zed" sorts after "Amy" by filename, but Amy's assessment is more recent;
    # latest must be chosen by the timestamp field, not the filename.
    (tmp_path / "Zed_old.json").write_text(
        '{"student_id": "Zed", "timestamp": "2026-01-01T10:00:00"}', encoding="utf-8")
    (tmp_path / "Amy_new.json").write_text(
        '{"student_id": "Amy", "timestamp": "2026-06-18T09:00:00"}', encoding="utf-8")
    assert storage.load_latest_record(tmp_path)["student_id"] == "Amy"


def test_load_latest_record_empty(tmp_path):
    assert storage.load_latest_record(tmp_path) is None


def test_count_and_delete_records_older_than(tmp_path):
    (tmp_path / "old.json").write_text(
        f'{{"student_id": "Old", "timestamp": "{_timestamp_days_ago(40)}"}}', encoding="utf-8")
    (tmp_path / "recent.json").write_text(
        f'{{"student_id": "Recent", "timestamp": "{_timestamp_days_ago(5)}"}}', encoding="utf-8")

    assert storage.count_records_older_than(30, tmp_path) == 1
    assert storage.count_records_older_than(60, tmp_path) == 0

    deleted = storage.delete_records_older_than(30, tmp_path)
    assert deleted == 1
    remaining = storage.list_records(tmp_path)
    assert len(remaining) == 1
    assert remaining[0]["student_id"] == "Recent"


def test_count_and_delete_records_older_than_skips_malformed_timestamp(tmp_path):
    (tmp_path / "bad_timestamp.json").write_text(
        '{"student_id": "Bad", "timestamp": "not-a-date"}', encoding="utf-8")

    assert storage.count_records_older_than(15, tmp_path) == 0
    assert storage.delete_records_older_than(15, tmp_path) == 0
    assert len(storage.list_records(tmp_path)) == 1
