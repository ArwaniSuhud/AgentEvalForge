"""Task file loading/validation (JSONL).

One task per line: {"id": str, "kind": str, "params": dict, "expected": dict}.
Blank lines are skipped. Any problem raises TaskValidationError (a
ValueError subclass) whose message contains the offending line number.
"""

from __future__ import annotations

import json
from pathlib import Path

__all__ = ["TaskValidationError", "load_tasks", "write_tasks"]


class TaskValidationError(ValueError):
    """Raised when a task file is invalid; message includes the line number."""


_REQUIRED_FIELDS = ("id", "kind", "params", "expected")


def _validate_task(obj: object, line_no: int) -> dict:
    if not isinstance(obj, dict):
        raise TaskValidationError(f"line {line_no}: task must be a JSON object")
    for field in _REQUIRED_FIELDS:
        if field not in obj:
            raise TaskValidationError(f"line {line_no}: missing field {field!r}")
    if not isinstance(obj["id"], str) or not obj["id"]:
        raise TaskValidationError(f"line {line_no}: field 'id' must be a non-empty str")
    if not isinstance(obj["kind"], str) or not obj["kind"]:
        raise TaskValidationError(f"line {line_no}: field 'kind' must be a non-empty str")
    if not isinstance(obj["params"], dict):
        raise TaskValidationError(f"line {line_no}: field 'params' must be a dict")
    if not isinstance(obj["expected"], dict):
        raise TaskValidationError(f"line {line_no}: field 'expected' must be a dict")
    return obj


def load_tasks(path) -> list[dict]:
    """Read a JSONL task file and return the list of validated task dicts."""
    path = Path(path)
    tasks: list[dict] = []
    seen_ids: set[str] = set()
    with path.open("r", encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh, start=1):
            if not raw.strip():
                continue  # blank lines are skipped
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise TaskValidationError(
                    f"line {line_no}: invalid JSON: {exc}"
                ) from exc
            task = _validate_task(obj, line_no)
            if task["id"] in seen_ids:
                raise TaskValidationError(f"line {line_no}: duplicate id {task['id']!r}")
            seen_ids.add(task["id"])
            tasks.append(task)
    return tasks


def write_tasks(path, tasks) -> None:
    """Write tasks back to a JSONL file (round-trip companion to load_tasks)."""
    path = Path(path)
    if path.parent and str(path.parent) not in ("", "."):
        path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for task in tasks:
            fh.write(json.dumps(task, ensure_ascii=False) + "\n")
