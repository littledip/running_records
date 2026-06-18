"""Tests for the passages manifest module (src/passages.py)."""
import json

import pytest

from src import passages


def _write(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def test_load_list_format(tmp_path):
    p = tmp_path / "passages.json"
    _write(p, [{"id": 1, "title": "A", "text": "x"}])
    assert passages.load_passages(p) == {1: {"id": 1, "title": "A", "text": "x"}}


def test_load_dict_format_injects_id(tmp_path):
    p = tmp_path / "passages.json"
    _write(p, {"g2": {"title": "B"}})
    loaded = passages.load_passages(p)
    assert loaded["g2"]["title"] == "B"
    assert loaded["g2"]["id"] == "g2"


def test_load_missing_returns_empty(tmp_path):
    assert passages.load_passages(tmp_path / "nope.json") == {}


def test_load_invalid_json_returns_empty(tmp_path):
    p = tmp_path / "passages.json"
    p.write_text("{bad json", encoding="utf-8")
    assert passages.load_passages(p) == {}


def test_get_passage(tmp_path):
    p = tmp_path / "passages.json"
    _write(p, [{"id": 1, "title": "A"}])
    assert passages.get_passage(1, p)["title"] == "A"
    assert passages.get_passage(99, p) is None


def test_save_passage_insert_update_and_keeps_list_format(tmp_path):
    p = tmp_path / "passages.json"
    _write(p, [{"id": 1, "title": "A"}])
    passages.save_passage({"id": 2, "title": "B"}, p)
    assert set(passages.load_passages(p)) == {1, 2}

    passages.save_passage({"id": 1, "title": "A2"}, p)
    assert passages.load_passages(p)[1]["title"] == "A2"
    assert isinstance(json.loads(p.read_text(encoding="utf-8")), list)  # never dict-keyed


def test_save_passage_requires_id(tmp_path):
    p = tmp_path / "passages.json"
    _write(p, [])
    with pytest.raises(ValueError):
        passages.save_passage({"title": "no id"}, p)


def test_delete_passages(tmp_path):
    p = tmp_path / "passages.json"
    _write(p, [{"id": 1}, {"id": 2}, {"id": 3}])
    removed = passages.delete_passages([1, 3], p)
    assert removed == 2
    assert set(passages.load_passages(p)) == {2}
