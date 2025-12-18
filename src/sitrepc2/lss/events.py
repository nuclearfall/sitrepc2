# src/sitrepc2/lss/events.py
from __future__ import annotations

from typing import Any, Iterable, List, Optional

from spacy.tokens import Doc

from .typedefs import WordMatch, EventMatch


# ---------------------------------------------------------------------
# WORD MATCHES
# ---------------------------------------------------------------------

def build_word_matches(raw_match: dict[str, Any]) -> list[WordMatch]:
    """
    Build WordMatch objects from a raw Holmes match dict.
    """
    result: list[WordMatch] = []

    for wm in raw_match.get("word_matches", []) or []:
        if "document_token_index" not in wm:
            raise ValueError(
                f"Holmes word_match missing document_token_index: {wm!r}"
            )

        def _get_int(key: str, default: int | None = None) -> int:
            val = wm.get(key, default)
            return 0 if val is None else int(val)

        def _get_opt_int(key: str) -> int | None:
            val = wm.get(key)
            return None if val is None else int(val)

        def _get_float(key: str, default: float = 1.0) -> float:
            try:
                return float(wm.get(key, default))
            except Exception:
                return default

        def _get_str(key: str, default: str = "") -> str:
            val = wm.get(key, default)
            return "" if val is None else str(val)

        result.append(
            WordMatch(
                search_phrase_token_index=_get_int("search_phrase_token_index", 0),
                search_phrase_word=_get_str("search_phrase_word"),

                document_token_index=_get_int("document_token_index"),
                first_document_token_index=_get_int(
                    "first_document_token_index",
                    _get_int("document_token_index"),
                ),
                last_document_token_index=_get_int(
                    "last_document_token_index",
                    _get_int("document_token_index"),
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
                    None if wm.get("extracted_word") is None
                    else str(wm.get("extracted_word"))
                ),
                depth=_get_int("depth", 0),
                explanation=(
                    None if wm.get("explanation") is None
                    else str(wm.get("explanation"))
                ),
            )
        )

    return result


# ---------------------------------------------------------------------
# SPAN COMPUTATION
# ---------------------------------------------------------------------

def _compute_doc_span(raw_match: dict[str, Any]) -> tuple[int, int]:
    """
    Compute [start, end) token indices for the overall event span.
    End index is exclusive.
    """
    word_matches = raw_match.get("word_matches", []) or []
    if not word_matches:
        return 0, 0

    starts: list[int] = []
    ends: list[int] = []

    for wm in word_matches:
        base = wm.get("document_token_index")
        if base is None:
            continue

        start = wm.get("first_document_token_index", base)
        end = wm.get("last_document_token_index", base)

        starts.append(int(start))
        ends.append(int(end))

    if not starts:
        return 0, 0

    return min(starts), max(ends) + 1


# ---------------------------------------------------------------------
# EVENT MATCH CONSTRUCTION
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# Public span helper (pipeline-facing)
# ---------------------------------------------------------------------

def compute_doc_span_from_raw_word_matches(
    raw_match: dict[str, Any],
) -> tuple[int, int]:
    """
    Public wrapper used by the LSS pipeline.

    Returns:
        (start_token, end_token) where end_token is exclusive.
    """
    return _compute_doc_span(raw_match)


def build_event_match(
    *,
    raw_match: dict[str, Any],
    doc: Doc,
    post_id: str,
) -> EventMatch:
    """
    Build a single EventMatch from a raw Holmes match dict.
    """
    start, end = _compute_doc_span(raw_match)

    text = (
        raw_match.get("sentences_within_document")
        or doc[start:end].text
    )

    return EventMatch(
        event_id=str(raw_match.get("event_id") or raw_match.get("id")),
        post_id=post_id,

        label=str(raw_match.get("label", "")),
        search_phrase_text=str(raw_match.get("search_phrase_text", "")),
        sentences_within_document=text,

        overall_similarity=float(
            raw_match.get("overall_similarity_measure", 1.0)
        ),
        negated=bool(raw_match.get("negated", False)),
        uncertain=bool(raw_match.get("uncertain", False)),
        involves_coreference=bool(
            raw_match.get("involves_coreference", False)
        ),

        doc_start_token_index=start,
        doc_end_token_index=end,

        word_matches=build_word_matches(raw_match),
        raw_match=raw_match,
    )


def build_event_matches(
    *,
    raw_matches: Iterable[dict[str, Any]],
    doc: Doc,
    post_id: str,
    min_similarity: float = 0.0,
) -> list[EventMatch]:
    """
    Build EventMatch objects for all raw Holmes matches for a document.
    """
    events: list[EventMatch] = []

    for raw in raw_matches:
        sim = float(raw.get("overall_similarity_measure", 1.0))
        if sim < min_similarity:
            continue

        events.append(
            build_event_match(
                raw_match=raw,
                doc=doc,
                post_id=post_id,
            )
        )

    return events
