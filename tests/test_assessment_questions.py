"""Tests for the assessment question bank module (src/assessment_questions.py)."""
import json

import pytest

from src import assessment_questions as aq


def _write(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def test_load_list_format(tmp_path):
    p = tmp_path / "assessment_questions.json"
    _write(p, [{"id": 1, "question_text": "What color was the rain?"}])
    assert aq.load_assessment_questions(p) == {1: {"id": 1, "question_text": "What color was the rain?"}}


def test_load_dict_format_injects_id(tmp_path):
    p = tmp_path / "assessment_questions.json"
    _write(p, {"q1": {"question_text": "B"}})
    loaded = aq.load_assessment_questions(p)
    assert loaded["q1"]["question_text"] == "B"
    assert loaded["q1"]["id"] == "q1"


def test_load_missing_returns_empty(tmp_path):
    assert aq.load_assessment_questions(tmp_path / "nope.json") == {}


def test_load_invalid_json_returns_empty(tmp_path):
    p = tmp_path / "assessment_questions.json"
    p.write_text("{bad json", encoding="utf-8")
    assert aq.load_assessment_questions(p) == {}


def test_get_assessment_question(tmp_path):
    p = tmp_path / "assessment_questions.json"
    _write(p, [{"id": 1, "question_text": "A"}])
    assert aq.get_assessment_question(1, p)["question_text"] == "A"
    assert aq.get_assessment_question(99, p) is None


def test_save_assessment_question_insert_update_and_keeps_list_format(tmp_path):
    p = tmp_path / "assessment_questions.json"
    _write(p, [{"id": 1, "question_text": "A"}])
    aq.save_assessment_question({"id": 2, "question_text": "B"}, p)
    assert set(aq.load_assessment_questions(p)) == {1, 2}

    aq.save_assessment_question({"id": 1, "question_text": "A2"}, p)
    assert aq.load_assessment_questions(p)[1]["question_text"] == "A2"
    assert isinstance(json.loads(p.read_text(encoding="utf-8")), list)  # never dict-keyed


def test_save_assessment_question_requires_id(tmp_path):
    p = tmp_path / "assessment_questions.json"
    _write(p, [])
    with pytest.raises(ValueError):
        aq.save_assessment_question({"question_text": "no id"}, p)


def test_delete_assessment_questions(tmp_path):
    p = tmp_path / "assessment_questions.json"
    _write(p, [{"id": 1}, {"id": 2}, {"id": 3}])
    removed = aq.delete_assessment_questions([1, 3], p)
    assert removed == 2
    assert set(aq.load_assessment_questions(p)) == {2}
