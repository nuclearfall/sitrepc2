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
