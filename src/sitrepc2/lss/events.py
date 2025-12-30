from __future__ import annotations

from typing import Iterable, List, Tuple

from spacy.tokens import Doc

from sitrepc2.lss.typedefs import EventMatch
from sitrepc2.lss.lss_scoping import (
    lss_scope_event,
    LSSRoleCandidate,
    LSSLocationSeries,
    LSSContextHint,
)


def compute_doc_span_from_phrase_match(raw: dict) -> Tuple[int, int]:
    """
    Compute the document-level token span for a Holmes PHRASE match.

    Notes:
    - Holmes internally exposes token alignment via the key `word_matches`
      (historical naming; these are NOT simple word hits).
    - This function treats them as structural token anchors only.

    Structural helper only:
    - no interpretation
    - no token objects
    - no semantic filtering
    """

    # Holmes internal field name (do not rename externally)
    token_alignments = raw.get("word_matches")
    if not token_alignments:
        raise ValueError("Holmes phrase match missing token alignments")

    starts: list[int] = []
    ends: list[int] = []

    for tm in token_alignments:
        # Holmes provides document token indices
        start = tm.get("document_token_index")
        length = tm.get("document_token_length", 1)

        if start is None:
            continue

        starts.append(start)
        ends.append(start + length)

    if not starts:
        raise ValueError("Unable to compute span from Holmes phrase match")

    return min(starts), max(ends)


def _sentence_span(doc: Doc, start: int, end: int) -> tuple[int, int]:
    """
    Return document token span of the sentence containing [start, end).
    """
    for sent in doc.sents:
        if sent.start <= start < sent.end:
            return sent.start, sent.end
    return start, end


def build_lss_events(
    *,
    doc: Doc,
    event_matches: Iterable[EventMatch],
    collect_nonspatial: bool = False,
) -> Tuple[
    List[
        Tuple[
            EventMatch,
            List[LSSRoleCandidate],
            List[LSSLocationSeries],
            List[LSSContextHint],
        ]
    ],
    List[EventMatch],
]:
    """
    Build STRUCTURALLY VALID LSS events from Holmes EVENT PHRASE matches.

    EVENT VALIDITY RULES (UPDATED, CANONICAL):
        - MUST have ≥ 1 role candidate (ACTOR / ACTION)
        - MUST have ≥ 1 location series overlapping
            EITHER:
              - event span
              - OR containing sentence span
        - context hints may be empty
    """

    valid_events = []
    rejected_nonspatial = []

    for ordinal, event in enumerate(event_matches):
        role_candidates, location_series, context_hints = lss_scope_event(
            doc=doc,
            event=event,
            event_ordinal=ordinal,
        )

        if not role_candidates:
            continue

        if not location_series:
            if collect_nonspatial:
                rejected_nonspatial.append(event)
            continue

        # -------------------------------------------------
        # SENTENCE-LEVEL SPATIAL VALIDATION (FIX)
        # -------------------------------------------------

        sent_start, sent_end = _sentence_span(
            doc,
            event.doc_start_token_index,
            event.doc_end_token_index,
        )

        def overlaps_sentence(series: LSSLocationSeries) -> bool:
            return not (
                series.end_token <= sent_start
                or series.start_token >= sent_end
            )

        if not any(overlaps_sentence(s) for s in location_series):
            if collect_nonspatial:
                rejected_nonspatial.append(event)
            continue

        valid_events.append(
            (
                event,
                role_candidates,
                location_series,
                context_hints,
            )
        )

    return valid_events, rejected_nonspatial
