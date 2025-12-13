# src/sitrepc2/lss/ids.py

from __future__ import annotations
import hashlib


def make_id(*parts: str) -> str:
    """
    Deterministic ID generator for LSS nodes.
    """
    h = hashlib.sha1()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"|")
    return h.hexdigest()
