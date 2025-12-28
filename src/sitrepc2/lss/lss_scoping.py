from __future__ import annotations

from dataclasses import dataclass
from typing import List

from spacy.tokens import Doc

from sitrepc2.lss.typedefs import EventMatch, WordMatch


# ---------------------------------------------------------------------
# LSS DATA CONTRACTS (STRUCTURAL, CANONICAL)
#
# IMPORTANT INVARIANTS:
# - RoleCandidates are semantic only (ACTOR / ACTION)
# - Locations are NEVER role candidates
# - Locations exist only as LocationItems inside LocationSeries
# - series_id and item_id are ORDINALS LOCAL TO A SINGLE EVENT
#   (they are NOT database IDs; persistence must remap them)
# - Context is attached at the LOWEST DEFENSIBLE STRUCTURAL LEVEL
# ---------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class LSSRoleCandidate:
    role_kind: str                 # ACTOR / ACTION
    text: str
    start_token: int
    end_token: int
    negated: bool
    uncertain: bool
    involves_coreference: bool
    similarity: float | None
    explanation: str | None = None


@dataclass(frozen=True, slots=True)
class LSSLocationItem:
    item_id: int                  # ordinal, local to event
    text: str
    start_token: int
    end_token: int


@dataclass(frozen=True, slots=True)
class LSSLocationSeries:
    series_id: int                # ordinal, local to event
    items: list[LSSLocationItem]
    start_token: int
    end_token: int


@dataclass(frozen=True, slots=True)
class LSSContextHint:
    ctx_kind: str                 # REGION / GROUP / DIRECTION
    text: str
    start_token: int
    end_token: int
    scope: str                    # LOCATION / SERIES / EVENT / SECTION / POST
    target_id: int | None         # item_id / series_id / event_ordinal / section_id / None
    source: str                   # GAZETTEER


SERIES_JOIN_TOKENS = {",", "and", "or", "&"}


# ---------------------------------------------------------------------
# TOP-LEVEL API
# ---------------------------------------------------------------------

def lss_scope_event(
    *,
    doc: Doc,
    event: EventMatch,
    event_ordinal: int,
    section_id: int | None = None,
) -> tuple[
    list[LSSRoleCandidate],
    list[LSSLocationSeries],
    list[LSSContextHint],
]:
    """
    Perform STRUCTURAL scoping for a single Holmes event.

    Returns three lists (never None):
        - role_candidates
        - location_series
        - context_hints
    """

    event_span = doc[event.doc_start_token_index : event.doc_end_token_index]
    assert (any(e.label_ == "LOCATION" for e in doc.ents)), "Not any LOCATION entity exists"
    assert any(
        e.label_ == "LOCATION"
        and e.start < event.doc_end_token_index
        and e.end > event.doc_start_token_index
        for e in doc.ents
    ), "No LOCATION entity overlaps Holmes event span"




    # -------------------------------------------------
    # ROLE CANDIDATES (HOLMES-DERIVED ONLY)
    # -------------------------------------------------

    role_candidates: list[LSSRoleCandidate] = []

    for wm in event.iter_content_words():
        rk = _infer_role_kind_from_pattern_element(wm)
        if rk is None:
            continue

        role_candidates.append(
            LSSRoleCandidate(
                role_kind=rk,
                text=wm.document_phrase or wm.document_word,
                start_token=wm.first_document_token_index,
                end_token=wm.last_document_token_index + 1,
                negated=wm.negated,
                uncertain=wm.uncertain,
                involves_coreference=wm.involves_coreference,
                similarity=wm.similarity_measure,
                explanation=wm.explanation,
            )
        )

    # -------------------------------------------------
    # LOCATION → LOCATION SERIES + ITEMS
    # -------------------------------------------------

    loc_ents = [e for e in doc.ents if e.label_ == "LOCATION"]
    loc_ents.sort(key=lambda e: e.start)

    location_series: list[LSSLocationSeries] = []
    current_items: list[LSSLocationItem] = []

    series_id = 0
    item_id = 0

    for ent in loc_ents:
        item = LSSLocationItem(
            item_id=item_id,
            text=ent.text,
            start_token=ent.start,
            end_token=ent.end,
        )
        item_id += 1

        if not current_items:
            current_items = [item]
            continue

        gap = doc[current_items[-1].end_token : item.start_token]
        if any(tok.text.lower() in SERIES_JOIN_TOKENS for tok in gap):
            current_items.append(item)
        else:
            location_series.append(
                LSSLocationSeries(
                    series_id=series_id,
                    items=current_items,
                    start_token=current_items[0].start_token,
                    end_token=current_items[-1].end_token,
                )
            )
            series_id += 1
            current_items = [item]

    if current_items:
        location_series.append(
            LSSLocationSeries(
                series_id=series_id,
                items=current_items,
                start_token=current_items[0].start_token,
                end_token=current_items[-1].end_token,
            )
        )

    # -------------------------------------------------
    # CONTEXT HINTS (FULL STRUCTURAL LATTICE)
    # -------------------------------------------------

    context_hints: list[LSSContextHint] = []

    for ent in doc.ents:
        if ent.label_ not in {"REGION", "GROUP", "DIRECTION"}:
            continue

        attached = False

        # LOCATION-LEVEL:
        # Only when context is fully CONTAINED within a single location span
        # (e.g., parenthetical: "Kupiansk (Kharkov Region)")
        for series in location_series:
            for item in series.items:
                if ent.start >= item.start_token and ent.end <= item.end_token:
                    context_hints.append(
                        LSSContextHint(
                            ctx_kind=ent.label_,
                            text=ent.text,
                            start_token=ent.start,
                            end_token=ent.end,
                            scope="LOCATION",
                            target_id=item.item_id,
                            source="GAZETTEER",
                        )
                    )
                    attached = True

        if attached:
            continue

        # SERIES-LEVEL:
        # Context overlaps series span but is NOT contained within a single item
        for series in location_series:
            if _spans_overlap(ent.start, ent.end, series.start_token, series.end_token):
                context_hints.append(
                    LSSContextHint(
                        ctx_kind=ent.label_,
                        text=ent.text,
                        start_token=ent.start,
                        end_token=ent.end,
                        scope="SERIES",
                        target_id=series.series_id,
                        source="GAZETTEER",
                    )
                )
                attached = True

        if attached:
            continue

        # EVENT-LEVEL:
        if _spans_overlap(ent.start, ent.end, event_span.start, event_span.end):
            context_hints.append(
                LSSContextHint(
                    ctx_kind=ent.label_,
                    text=ent.text,
                    start_token=ent.start,
                    end_token=ent.end,
                    scope="EVENT",
                    target_id=event_ordinal,
                    source="GAZETTEER",
                )
            )
            continue

        # SECTION-LEVEL:
        if section_id is not None:
            context_hints.append(
                LSSContextHint(
                    ctx_kind=ent.label_,
                    text=ent.text,
                    start_token=ent.start,
                    end_token=ent.end,
                    scope="SECTION",
                    target_id=section_id,
                    source="GAZETTEER",
                )
            )
            continue

        # POST-LEVEL (fallback)
        context_hints.append(
            LSSContextHint(
                ctx_kind=ent.label_,
                text=ent.text,
                start_token=ent.start,
                end_token=ent.end,
                scope="POST",
                target_id=None,
                source="GAZETTEER",
            )
        )

    return role_candidates, location_series, context_hints


# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------

def _spans_overlap(a1: int, a2: int, b1: int, b2: int) -> bool:
    return not (a2 <= b1 or b2 <= a1)


def _infer_role_kind_from_pattern_element(wm: WordMatch) -> str | None:
    mt = (wm.match_type or "").lower()

    if mt in {"subject", "actor", "object", "dobj", "possessor"}:
        return "ACTOR"

    if mt in {"verb", "action"}:
        return "ACTION"

    return None
