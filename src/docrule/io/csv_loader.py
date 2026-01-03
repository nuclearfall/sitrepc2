from __future__ import annotations

from pathlib import Path
from typing import List, Optional
import csv


def _detect_delimiter(sample: str) -> str:
    """
    Attempt to detect a CSV delimiter from a text sample.
    """
    try:
        dialect = csv.Sniffer().sniff(sample)
        return dialect.delimiter
    except Exception:
        return ","


def load_csv_text(
    path: Path,
    text_column: str,
    delimiter: Optional[str] = None,
) -> str:
    """
    Load text from a CSV file using the given column header.

    All extracted entries are concatenated with double line breaks.

    Args:
        text_column: Column name containing text
        delimiter: Optional delimiter override

    Raises:
        ValueError on parse or extraction failure.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception as exc:
        raise ValueError(f"Failed to read CSV file: {path}") from exc

    if not raw.strip():
        return ""

    if delimiter is None:
        delimiter = _detect_delimiter(raw[:1024])

    try:
        reader = csv.DictReader(
            raw.splitlines(),
            delimiter=delimiter,
        )
    except Exception as exc:
        raise ValueError(f"Failed to parse CSV file: {path}") from exc

    if text_column not in reader.fieldnames:
        raise KeyError(
            f"Column '{text_column}' not found in CSV file {path}"
        )

    entries: List[str] = []
    for row_idx, row in enumerate(reader, start=1):
        value = row.get(text_column)
        if value:
            entries.append(str(value))

    return "\n\n".join(entries)
