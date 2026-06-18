"""Passage manifest access — load/lookup/save/delete.

Replaces the `load_passages` copy that was duplicated across home.py,
student_record.py and teacher_admin.py. Accepts both the shipped list format
and a dict-keyed format on read; always writes the list format so passage ids
keep their native type (the dict format turns int ids into JSON string keys).
No Streamlit imports.
"""
import json
from pathlib import Path
from typing import Any

from .config import PASSAGES_FILE


def _read_items(path: Path = PASSAGES_FILE) -> list[dict]:
    """Return passages as a list of dicts, tolerating both file formats."""
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return [p for p in data if isinstance(p, dict)]
    if isinstance(data, dict):
        # dict-keyed → list, ensuring each item carries its id
        return [{"id": k, **v} for k, v in data.items() if isinstance(v, dict)]
    return []


def _write_items(items: list[dict], path: Path = PASSAGES_FILE) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)


def load_passages(path: Path = PASSAGES_FILE) -> dict[Any, dict]:
    """Return passages keyed by id for easy lookup (empty dict if none/invalid)."""
    try:
        items = _read_items(path)
    except json.JSONDecodeError:
        return {}
    return {p.get("id"): p for p in items}


def get_passage(passage_id: Any, path: Path = PASSAGES_FILE) -> dict | None:
    """Return a single passage by id, or None."""
    return load_passages(path).get(passage_id)


def save_passage(passage: dict, path: Path = PASSAGES_FILE) -> None:
    """Insert or update a passage (matched by 'id'), preserving list format."""
    if "id" not in passage:
        raise ValueError("passage must include an 'id'")
    items = [p for p in _read_items(path) if p.get("id") != passage["id"]]
    items.append(passage)
    _write_items(items, path)


def delete_passages(ids: list[Any], path: Path = PASSAGES_FILE) -> int:
    """Delete passages whose id is in `ids`. Returns the number removed."""
    targets = set(ids)
    items = _read_items(path)
    kept = [p for p in items if p.get("id") not in targets]
    _write_items(kept, path)
    return len(items) - len(kept)
