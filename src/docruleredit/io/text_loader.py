from __future__ import annotations

from pathlib import Path


def load_text_file(path: Path) -> str:
    """
    Load a plain text file and return its contents.

    Raises:
        ValueError if the file cannot be read.
    """
    try:
        return path.read_text(encoding="utf-8")
    except Exception as exc:
        raise ValueError(f"Failed to read text file: {path}") from exc
