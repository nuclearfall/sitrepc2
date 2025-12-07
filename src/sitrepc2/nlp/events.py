# src/sitrepc2/holmes/events.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, List

import holmes_extractor as holmes


@dataclass(frozen=True, slots=True)
class HolmesWordMatch:
    """
    Thin wrapper around one entry from the 'word_matches' list in the
    dictionary returned by Holmes Manager.match().

    This mirrors the documented properties in 6.7 as far as we care
    about them right now.
    """

    search_phrase_token_index: int
    search_phrase_word: str

    document_token_index: int
    first_document_token_index: int
    last_document_token_index: int
    structurally_matched_document_token_index: int

    document_subword_index: int | None
    document_subword_containing_token_index: int | None

    document_word: str
    document_phrase: str

    match_type: str
    negated: bool
    uncertain: bool
    similarity_measure: float
    involves_coreference: bool

    extracted_word: str | None
    depth: int
    explanation: str | None


@dataclass(frozen=True, slots=True)
class HolmesEventMatch:
    """
    High-level wrapper around a single Holmes match dict for structural
    extraction use.

    We store Holmes' own human-readable context instead of re-slicing
    the Doc for text: `sentences_within_document` is the raw text of
    the matching sentence(s), and `search_phrase_text` is the phrase
    that was matched.
    """

    event_id: str
    post_id: str

    label: str
    search_phrase_text: str
    sentences_within_document: str

    overall_similarity: float
    negated: bool
    uncertain: bool
    involves_coreference: bool

    doc_start_token_index: int
    doc_end_token_index: int

    word_matches: list[HolmesWordMatch]
    raw_match: dict[str, Any] | None = None

    def iter_content_words(self) -> Iterable[HolmesWordMatch]:
        """
        Yield word-matches that are not generic placeholders like
        'somebody'/'something'.
        """
        for wm in self.word_matches:
            if wm.document_word.lower() in {"somebody", "something"}:
                continue
            yield wm


def build_word_matches(raw_match: dict[str, Any]) -> list[HolmesWordMatch]:
    """
    Build HolmesWordMatch objects from a raw Holmes match dict
    (the single dict from Manager.match()).
    """
    result: list[HolmesWordMatch] = []
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

        wp = HolmesWordMatch(
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
