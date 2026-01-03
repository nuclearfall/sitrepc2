from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, List
import json


def _extract_text_from_obj(obj: Any, key: str) -> List[str]:
    """
    Extract text values from a JSON object using a key.

    Supports:
    - dicts
    - lists of dicts
    """
    values: List[str] = []

    if isinstance(obj, dict):
        if key not in obj:
            raise KeyError(f"Key '{key}' not found in JSON object")
        value = obj[key]
        if value is not None:
            values.append(str(value))

    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            if not isinstance(item, dict):
                raise ValueError(
                    f"Expected object at index {idx}, got {type(item)}"
                )
            if key not in item:
                raise KeyError(
                    f"Key '{key}' not found in JSON object at index {idx}"
                )
            value = item[key]
            if value is not None:
                values.append(str(value))

    else:
        raise ValueError(f"Unsupported JSON root type: {type(obj)}")

    return values


def load_json_text(path: Path, text_key: str) -> str:
    """
    Load text from a JSON or JSONL file using the given key.

    All extracted entries are concatenated with double line breaks.

    Raises:
        ValueError / KeyError on parse or extraction failure.
    """
    entries: List[str] = []

    try:
        raw = path.read_text(encoding="utf-8")
    except Exception as exc:
        raise ValueError(f"Failed to read JSON file: {path}") from exc

    raw = raw.strip()
    if not raw:
        return ""

    # Heuristic: JSONL if file has multiple top-level lines
    if "\n" in raw:
        for lineno, line in enumerate(raw.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON on line {lineno} in {path}"
                ) from exc
            entries.extend(_extract_text_from_obj(obj, text_key))
    else:
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {path}") from exc
        entries.extend(_extract_text_from_obj(obj, text_key))

    return "\n\n".join(entries)
