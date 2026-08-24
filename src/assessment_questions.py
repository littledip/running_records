"""Assessment question bank access — load/lookup/save/delete.

A standalone question bank, not tied to any specific passage. Mirrors
src/passages.py's manifest pattern. No Streamlit imports.
"""
import json
from pathlib import Path
from typing import Any

from .config import ASSESSMENT_QUESTIONS_FILE


def _read_items(path: Path = ASSESSMENT_QUESTIONS_FILE) -> list[dict]:
    """Return questions as a list of dicts, tolerating both file formats."""
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return [q for q in data if isinstance(q, dict)]
    if isinstance(data, dict):
        # dict-keyed → list, ensuring each item carries its id
        return [{"id": k, **v} for k, v in data.items() if isinstance(v, dict)]
    return []


def _write_items(items: list[dict], path: Path = ASSESSMENT_QUESTIONS_FILE) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)


def load_assessment_questions(path: Path = ASSESSMENT_QUESTIONS_FILE) -> dict[Any, dict]:
    """Return questions keyed by id for easy lookup (empty dict if none/invalid)."""
    try:
        items = _read_items(path)
    except json.JSONDecodeError:
        return {}
    return {q.get("id"): q for q in items}


def get_assessment_question(question_id: Any, path: Path = ASSESSMENT_QUESTIONS_FILE) -> dict | None:
    """Return a single question by id, or None."""
    return load_assessment_questions(path).get(question_id)


def save_assessment_question(question: dict, path: Path = ASSESSMENT_QUESTIONS_FILE) -> None:
    """Insert or update a question (matched by 'id'), preserving list format."""
    if "id" not in question:
        raise ValueError("question must include an 'id'")
    items = [q for q in _read_items(path) if q.get("id") != question["id"]]
    items.append(question)
    _write_items(items, path)


def delete_assessment_questions(ids: list[Any], path: Path = ASSESSMENT_QUESTIONS_FILE) -> int:
    """Delete questions whose id is in `ids`. Returns the number removed."""
    targets = set(ids)
    items = _read_items(path)
    kept = [q for q in items if q.get("id") not in targets]
    _write_items(kept, path)
    return len(items) - len(kept)
