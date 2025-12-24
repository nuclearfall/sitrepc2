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


def compute_doc_span_from_raw_word_matches(raw: dict) -> Tuple[int, int]:
    """
    Compute the document-level token span for a Holmes match.

    Structural helper only:
    - no interpretation
    - no word objects
    - no semantic filtering
    """

    word_matches = raw.get("word_matches")
    if not word_matches:
        raise ValueError("Holmes match missing word_matches")

    starts = []
    ends = []

    for wm in word_matches:
        # Holmes provides document token indices
        start = wm.get("document_token_index")
        length = wm.get("document_token_length", 1)

        if start is None:
            continue

        starts.append(start)
        ends.append(start + length)

    if not starts:
        raise ValueError("Unable to compute span from Holmes word_matches")

    return min(starts), max(ends)
    
def build_lss_events(
    *,
    doc: Doc,
    event_matches: Iterable[EventMatch],
) -> List[
    Tuple[
        EventMatch,
        List[LSSRoleCandidate],
        List[LSSLocationSeries],
        List[LSSContextHint],
    ]
]:
    """
    Build STRUCTURALLY VALID LSS events.

    EVENT VALIDITY RULES (CANONICAL):
        - MUST have ≥ 1 role candidate (ACTOR / ACTION)
        - MUST have ≥ 1 location series
        - context hints may be empty
    """

    out: list[
        Tuple[
            EventMatch,
            List[LSSRoleCandidate],
            List[LSSLocationSeries],
            List[LSSContextHint],
        ]
    ] = []

    for ordinal, event in enumerate(event_matches):
        role_candidates, location_series, context_hints = lss_scope_event(
            doc=doc,
            event=event,
            event_ordinal=ordinal,
        )

        # -------------------------------------------------
        # STRUCTURAL EVENT VALIDATION
        # -------------------------------------------------

        if not role_candidates:
            continue

        if not location_series:
            continue

        out.append(
            (
                event,
                role_candidates,
                location_series,
                context_hints,
            )
        )

    return out
