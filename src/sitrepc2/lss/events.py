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

    EVENT VALIDITY RULES (CANONICAL):
        - MUST have ≥ 1 role candidate (ACTOR / ACTION)
        - MUST have ≥ 1 location series
        - context hints may be empty

    Optional behavior:
        - If collect_nonspatial=True, Holmes event matches that fail
          the LOCATION requirement are returned separately for audit/debug.
        - Non-spatial matches are NEVER promoted to LSS events.

    Returns:
        (valid_lss_events, rejected_nonspatial_events)
    """

    valid_events: list[
        Tuple[
            EventMatch,
            List[LSSRoleCandidate],
            List[LSSLocationSeries],
            List[LSSContextHint],
        ]
    ] = []

    rejected_nonspatial: list[EventMatch] = []

    for ordinal, event in enumerate(event_matches):
        role_candidates, location_series, context_hints = lss_scope_event(
            doc=doc,
            event=event,
            event_ordinal=ordinal,
        )

        # -------------------------------------------------
        # STRUCTURAL EVENT VALIDATION (LSS CANONICAL)
        # -------------------------------------------------

        if not role_candidates:
            continue

        if not location_series:
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