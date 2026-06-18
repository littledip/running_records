"""Tests for the assessment-record repository (src/storage.py)."""
from src import storage


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


def test_load_latest_record(tmp_path):
    # Filenames carry a timestamp prefix; list/latest order by that name.
    (tmp_path / "A_20260101_100000.json").write_text('{"student_id": "A"}', encoding="utf-8")
    (tmp_path / "B_20260101_100001.json").write_text('{"student_id": "B"}', encoding="utf-8")
    assert storage.load_latest_record(tmp_path)["student_id"] == "B"


def test_load_latest_record_empty(tmp_path):
    assert storage.load_latest_record(tmp_path) is None
