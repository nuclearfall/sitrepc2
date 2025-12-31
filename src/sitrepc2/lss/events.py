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


# ---------------------------------------------------------------------
# DEBUG HELPERS
# ---------------------------------------------------------------------

def _dbg(msg: str) -> None:
    print(f"[LSS][events] {msg}", flush=True)


# ---------------------------------------------------------------------
# HOLMES SPAN HELPER
# ---------------------------------------------------------------------

def compute_doc_span_from_phrase_match(raw: dict) -> Tuple[int, int]:
    """
    Compute the document-level token span for a Holmes PHRASE match.
    """

    token_alignments = raw.get("word_matches")
    if not token_alignments:
        raise ValueError("Holmes phrase match missing token alignments")

    starts: list[int] = []
    ends: list[int] = []

    for tm in token_alignments:
        start = tm.get("document_token_index")
        length = tm.get("document_token_length", 1)

        if start is None:
            continue

        starts.append(start)
        ends.append(start + length)

    if not starts:
        raise ValueError("Unable to compute span from Holmes phrase match")

    return min(starts), max(ends)


# ---------------------------------------------------------------------
# EVENT BUILDER (INSTRUMENTED)
# ---------------------------------------------------------------------

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
    """

    event_matches = list(event_matches)
    _dbg(f"Received {len(event_matches)} EventMatch objects")

    valid_events = []
    rejected = []

    for ordinal, event in enumerate(event_matches):
        _dbg(
            f"EVENT[{ordinal}] "
            f"label={event.label!r} "
            f"similarity={event.overall_similarity:.3f} "
            f"tokens=({event.doc_start_token_index}, {event.doc_end_token_index})"
        )

        sent = doc[event.doc_start_token_index].sent
        _dbg(f"  sentence: {sent.text.strip()}")

        role_candidates, location_series, context_hints = lss_scope_event(
            doc=doc,
            event=event,
            event_ordinal=ordinal,
        )

        _dbg(f"  roles={len(role_candidates)}")
        for rc in role_candidates:
            _dbg(
                f"    ROLE {rc.role_kind} "
                f"[{rc.start_token},{rc.end_token}): {rc.text!r}"
            )

        _dbg(f"  location_series={len(location_series)}")
        for s in location_series:
            items = ", ".join(it.text for it in s.items)
            _dbg(
                f"    SERIES[{s.series_id}] "
                f"[{s.start_token},{s.end_token}): {items}"
            )

        _dbg(f"  context_hints={len(context_hints)}")
        for ch in context_hints:
            _dbg(
                f"    CTX {ch.ctx_kind} "
                f"scope={ch.scope} "
                f"target={ch.target_id} "
                f"text={ch.text!r}"
            )

        if not role_candidates:
            _dbg("  -> REJECTED (no role candidates)")
            if collect_nonspatial:
                rejected.append(event)
            continue

        _dbg("  -> ACCEPTED")
        valid_events.append(
            (
                event,
                role_candidates,
                location_series,
                context_hints,
            )
        )

    _dbg(f"Returning {len(valid_events)} valid events")
    return valid_events, rejected
