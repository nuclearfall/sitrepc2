from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from spacy.tokens import Doc, Span

from sitrepc2.lss.typedefs import EventMatch, PhraseMatch


# ---------------------------------------------------------------------
# LSS DATA CONTRACTS (STRUCTURAL, CANONICAL)
#
# IMPORTANT INVARIANTS:
# - RoleCandidates are semantic only (ACTOR / ACTION)
# - Locations are NEVER role candidates
# - Locations exist only as LocationItems inside LocationSeries
# - series_id and item_id are ORDINALS LOCAL TO A SINGLE EVENT
# - Context is attached at the LOWEST DEFENSIBLE STRUCTURAL LEVEL
# ---------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class LSSRoleCandidate:
    role_kind: str                 # ACTOR / ACTION
    text: str
    start_token: int
    end_token: int
    match_type: str
    negated: bool
    uncertain: bool
    involves_coreference: bool
    similarity: float
    explanation: str


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
    ctx_kind: str                 # REGION / GROUP / DIRECTION / etc
    text: str
    start_token: Optional[int]
    end_token: Optional[int]
    scope: str                    # LOCATION / SERIES / EVENT / SECTION / POST
    target_id: Optional[int]      # item_id / series_id / event_id / section_id / None
    source: str                   # GAZETTEER | HOLMES | SYNTHETIC

    # -----------------------------------------------------------------
    # ADDITIVE API (SAFE)
    # -----------------------------------------------------------------

    @classmethod
    def from_holmes_match(
        cls,
        *,
        raw: dict,
        doc: Doc,
    ) -> "LSSContextHint":
        """
        Construct a CONTEXT hint directly from a Holmes CONTEXT:* match.

        This method is ADDITIVE:
        - No existing callers are affected
        - Used only by the pipeline
        - Scope defaults to POST; contextualize() will refine
        """

        label = raw.get("search_phrase_label", "")
        assert label.startswith("CONTEXT:"), label

        token_alignments = raw.get("word_matches") or []
        starts: list[int] = []
        ends: list[int] = []

        for tm in token_alignments:
            start = tm.get("document_token_index")
            length = tm.get("document_token_length", 1)
            if start is not None:
                starts.append(start)
                ends.append(start + length)

        if starts:
            start_token = min(starts)
            end_token = max(ends)
            text = doc[start_token:end_token].text
        else:
            start_token = None
            end_token = None
            text = raw.get("search_phrase_text", "") or ""

        return cls(
            ctx_kind=label[len("CONTEXT:"):],
            text=text,
            start_token=start_token,
            end_token=end_token,
            scope="POST",
            target_id=None,
            source="HOLMES",
        )


SERIES_JOIN_TOKENS = {",", "and", "or", "&"}


# ---------------------------------------------------------------------
# TOP-LEVEL API
# ---------------------------------------------------------------------

def spans_by_label(doc, label, group: str = None):
    source = doc.ents if group is None else doc.spans.get(group, [])
    return [span for span in source if span.label_ == label]


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
    """

    # -------------------------------------------------
    # EVENT WINDOW (sentence-bounded)
    # -------------------------------------------------

    sent = doc[event.doc_start_token_index].sent
    event_start = sent.start
    event_end = sent.end

    # -------------------------------------------------
    # ROLE CANDIDATES
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
                match_type=wm.match_type,
                negated=wm.negated,
                uncertain=wm.uncertain,
                involves_coreference=wm.involves_coreference,
                similarity=wm.similarity,
                explanation=wm.explanation,
            )
        )

    # -------------------------------------------------
    # LOCATION SERIES (EVENT-LOCAL)
    # -------------------------------------------------

    loc_ents = [
        e for e in doc.ents
        if e.label_ == "LOCATION"
        and _spans_overlap(e.start, e.end, event_start, event_end)
    ]

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
    # CONTEXT HINTS (GAZETTEER-BASED)
    # -------------------------------------------------

    context_hints: list[LSSContextHint] = []

    for ent in doc.ents:
        if ent.label_ not in {"REGION", "GROUP", "DIRECTION"}:
            continue

        attached = False

        # ---------------------------------------------
        # LOCATION (contained-in-item)
        # ---------------------------------------------

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

        # ---------------------------------------------
        # LOCATION (retroactive series qualifier)
        # ---------------------------------------------

        attached = _apply_retroactive_series_qualifier(
            doc=doc,
            location_series=location_series,
            ctx_ent=ent,
            context_hints=context_hints,
        )
        if attached:
            continue

        # ---------------------------------------------
        # SERIES
        # ---------------------------------------------

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

        # ---------------------------------------------
        # EVENT
        # ---------------------------------------------

        if _spans_overlap(ent.start, ent.end, event_start, event_end):
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

        # ---------------------------------------------
        # SECTION / POST
        # ---------------------------------------------

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
        else:
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


def _infer_role_kind_from_pattern_element(wm: PhraseMatch) -> str | None:
    mt = (wm.match_type or "").lower()

    if mt in {"subject", "actor", "object", "dobj", "possessor"}:
        return "ACTOR"

    if mt in {"verb", "action"}:
        return "ACTION"

    return None


def _apply_retroactive_series_qualifier(
    *,
    doc: Doc,
    location_series: list[LSSLocationSeries],
    ctx_ent: Span,
    context_hints: list[LSSContextHint],
) -> bool:
    """
    Retroactive REGION/GROUP/DIRECTION qualifiers partition a location series.
    Each applies only to items since the previous qualifier of the same kind.
    """

    kind = ctx_ent.label_
    ctx_start = ctx_ent.start
    ctx_end = ctx_ent.end

    for series in location_series:
        items = series.items
        if not items:
            continue

        last_item_before = None
        for it in items:
            if it.end_token <= ctx_start:
                last_item_before = it
            else:
                break

        if last_item_before is None:
            continue

        series_starts = {it.start_token for it in items}
        for ent in doc.ents:
            if ent.label_ != "LOCATION":
                continue
            if last_item_before.end_token <= ent.start < ctx_start:
                if ent.start not in series_starts:
                    return False

        cutoff = series.start_token
        for ch in context_hints:
            if (
                ch.ctx_kind == kind
                and ch.scope == "LOCATION"
                and ch.start_token is not None
                and ch.start_token < ctx_start
                and any(it.item_id == ch.target_id for it in items)
            ):
                cutoff = max(cutoff, ch.start_token)

        for it in items:
            if it.start_token >= cutoff and it.end_token <= ctx_start:
                context_hints.append(
                    LSSContextHint(
                        ctx_kind=kind,
                        text=ctx_ent.text,
                        start_token=ctx_start,
                        end_token=ctx_end,
                        scope="LOCATION",
                        target_id=it.item_id,
                        source="GAZETTEER",
                    )
                )

        return True

    return False
