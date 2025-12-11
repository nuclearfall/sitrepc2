# src/sitrepc2/events/context/base.py

from __future__ import annotations
from typing import List

def normalize(txt: str | None) -> str:
    """Lowercase normalization helper."""
    if not txt:
        return ""
    return txt.strip().lower()

def matches_alias(text: str, name: str, aliases: List[str]) -> bool:
    text = normalize(text)
    if text == normalize(name):
        return True
    return text in {normalize(a) for a in aliases}
