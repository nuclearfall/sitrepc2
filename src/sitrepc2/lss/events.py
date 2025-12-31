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


def _dbg(msg: str) -> None:
    print(f"[LSS][events] {msg}", flush=True)


def compute_doc_span_from_phrase_match(raw: dict) -> Tuple[int, int]:
    token_alignments = raw.get("word_matches")
    if not token_alignments:
        raise ValueError("Holmes phrase match missing token alignments")

    starts, ends = [], []
    for tm in token_alignments:
        start = tm.get("document_token_index")
        length = tm.get("document_token_length", 1)
        if start is not None:
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
    event_matches = list(event_matches)
    _dbg(f"Received {len(event_matches)} EventMatch objects")

    valid_events: list = []
    rejected: list = []

    for ordinal, event in enumerate(event_matches):
        _dbg(
            f"EVENT[{ordinal}] label={event.label!r} "
            f"tokens=({event.doc_start_token_index},{event.doc_end_token_index})"
        )

        sent = doc[event.doc_start_token_index].sent
        _dbg(f"  sentence: {sent.text.strip()}")

        roles, series, hints = lss_scope_event(
            doc=doc,
            event=event,
            event_ordinal=ordinal,
        )

        _dbg(f"  roles={len(roles)}")
        _dbg(f"  location_series={len(series)}")
        _dbg(f"  context_hints={len(hints)}")

        # -------------------------------------------------
        # IMPORTANT CHANGE:
        # Do NOT reject events with no role candidates
        # -------------------------------------------------

        valid_events.append((event, roles, series, hints))
        _dbg("  -> ACCEPTED")

    _dbg(f"Returning {len(valid_events)} valid events")
    return valid_events, rejected
