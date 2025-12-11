# src/sitrepc2/holmes/events.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, List

import holmes_extractor as holmes

from .typedefs import WordMatch


def build_word_matches(raw_match: dict[str, Any]) -> list[WordMatch]:
    """
    Build WordMatch objects from a raw Holmes match dict
    (the single dict from Manager.match()).
    """
    result: list[WordMatch] = []
    for wm in raw_match.get("word_matches", []) or []:
        # Required core index; if it's missing, something is badly wrong
        if "document_token_index" not in wm:
            raise ValueError(f"Holmes word_match missing document_token_index: {wm!r}")

        def _get_int(key: str, default: int | None = None) -> int:
            val = wm.get(key, default)
            if val is None:
                return 0
            return int(val)

        def _get_opt_int(key: str) -> int | None:
            val = wm.get(key)
            if val is None:
                return None
            return int(val)

        def _get_float(key: str, default: float = 1.0) -> float:
            val = wm.get(key, default)
            try:
                return float(val)
            except Exception:
                return default

        def _get_str(key: str, default: str = "") -> str:
            val = wm.get(key, default)
            return "" if val is None else str(val)

        wp = WordMatch(
            search_phrase_token_index=_get_int("search_phrase_token_index", 0),
            search_phrase_word=_get_str("search_phrase_word"),

            document_token_index=_get_int("document_token_index"),
            first_document_token_index=_get_int(
                "first_document_token_index", _get_int("document_token_index")
            ),
            last_document_token_index=_get_int(
                "last_document_token_index", _get_int("document_token_index")
            ),
            structurally_matched_document_token_index=_get_int(
                "structurally_matched_document_token_index",
                _get_int("document_token_index"),
            ),

            document_subword_index=_get_opt_int("document_subword_index"),
            document_subword_containing_token_index=_get_opt_int(
                "document_subword_containing_token_index"
            ),

            document_word=_get_str("document_word"),
            document_phrase=_get_str("document_phrase"),

            match_type=_get_str("match_type"),
            negated=bool(wm.get("negated", False)),
            uncertain=bool(wm.get("uncertain", False)),
            similarity_measure=_get_float("similarity_measure", 1.0),
            involves_coreference=bool(wm.get("involves_coreference", False)),

            extracted_word=(
                None
                if wm.get("extracted_word") is None
                else str(wm.get("extracted_word"))
            ),
            depth=_get_int("depth", 0),
            explanation=(
                None
                if wm.get("explanation") is None
                else str(wm.get("explanation"))
            ),
        )
        result.append(wp)
    return result


def compute_doc_span_from_raw_word_matches(
    raw_match: dict[str, Any],
) -> tuple[int, int]:
    """
    Compute [start, end) token indices for the overall match span.

    Uses first_document_token_index / last_document_token_index from
    each word_match, falling back to document_token_index. End index
    is exclusive (Shunting to doc[start:end]).
    """
    word_matches = raw_match.get("word_matches", []) or []
    if not word_matches:
        return 0, 0

    first_indices: list[int] = []
    last_indices: list[int] = []

    for wm in word_matches:
        base_idx = wm.get("document_token_index")
        if base_idx is None:
            continue

        first = wm.get("first_document_token_index", base_idx)
        last = wm.get("last_document_token_index", base_idx)

        first_indices.append(int(first))
        last_indices.append(int(last))

    if not first_indices:
        return 0, 0

    start = min(first_indices)
    end = max(last_indices) + 1  # Holmes last index is inclusive
    return start, end
