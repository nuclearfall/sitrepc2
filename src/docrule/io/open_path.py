from __future__ import annotations

from pathlib import Path
from typing import Optional

from .text_loader import load_text_file
from .json_loader import load_json_text
from .csv_loader import load_csv_text


class NeedsUserInput(Exception):
    """Raised when file requires user-specified key / column."""


def open_path(
    path: Path,
    *,
    json_key: str = "text",
    csv_column: str = "text",
    csv_delimiter: Optional[str] = None,
) -> str:
    """
    Unified file loader.

    Assumptions:
    - JSON / JSONL → field "text"
    - CSV → column "text", auto-detected delimiter

    Raises:
        NeedsUserInput if required field/column not found.
    """
    if not path.exists():
        raise FileNotFoundError(path)

    suffix = path.suffix.lower()

    # ---- Plain text --------------------------------------------------
    if suffix in {".txt", ".md"}:
        return load_text_file(path)

    # ---- JSON / JSONL ------------------------------------------------
    if suffix in {".json", ".jsonl"}:
        try:
            return load_json_text(path, json_key)
        except KeyError:
            raise NeedsUserInput("JSON key missing")

    # ---- CSV ---------------------------------------------------------
    if suffix == ".csv":
        try:
            return load_csv_text(path, csv_column, csv_delimiter)
        except KeyError:
            raise NeedsUserInput("CSV column missing")

    # ---- Fallback ----------------------------------------------------
    return load_text_file(path)
