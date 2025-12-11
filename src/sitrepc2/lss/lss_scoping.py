# sitrepc2/nlp/lss_scoping.py
"""
Lexical–Semantic–Syntactic Layer (LSS)
Location & Context Scoping Module

This performs:
    • extraction of LOCALE / REGION / GROUP / DIRECTION / PROXIMITY spans
    • detection of ACTOR and ACTION
    • location construction (no Gazetteer resolution yet)
    • location-level context assignment
    • event-level context assignment
    • identification of veiled context (e.g., “in the Kupyansk direction”)

DOM will later apply filtering, scoring, candidate elimination, etc.
"""

from __future__ import annotations
from typing import List, Optional, Tuple

from spacy.tokens import Doc, Span
from holmes_extractor import Manager

from sitrepc2.lss.typedefs import EventMatch
from sitrepc2.events.typedefs import (
    Location,
    LocaleCandidate,
    SitRepContext,
    CtxKind,
    Actor, ActorKind,
    Action, ActionKind,
)

# ---------------------------------------------------------------------------
# Top-level API
# ---------------------------------------------------------------------------

def lss_scope_event(
    doc: Doc,
    hem: EventMatch,
) -> Tuple[List[Location], List[SitRepContext], Optional[Actor], Optional[Action]]:
    """
    Main entry point for LSS scoping.
    Returns a 4-tuple:
        locations:      list[Location]                  (each with location-level contexts)
        event_contexts: list[SitRepContext]             (apply to whole event)
        actor:          Optional[Actor]
        action:         Optional[Action]

    Responsibilities:
        - extract all span-level entities from spaCy (via entity ruler)
        - classify spans: LOCALE / REGION / GROUP / DIRECTION / PROXIMITY
        - create Location objects for LOCALE spans
        - determine which contexts scope which locations
        - assign event-wide contexts
    """

    event_tokens = doc[hem.doc_start_token_index: hem.doc_end_token_index]
    spans = _extract_relevant_spans(event_tokens)

    # Build preliminary structures
    location_objs = _build_location_objects(spans)
    actor = _extract_actor(spans)
    action = _extract_action(hem)

    # Two context lists: location-level and event-level
    event_contexts: List[SitRepContext] = []

    # Perform context scoping
    _assign_context_to_locations_and_event(
        spans,
        location_objs,
        event_contexts,
    )

    return location_objs, event_contexts, actor, action


# ---------------------------------------------------------------------------
# Span Extraction
# ---------------------------------------------------------------------------

def _extract_relevant_spans(tokens: Span) -> List[Span]:
    """
    Extract only the spans created by the entity-ruler:
        LOCALE
        REGION
        GROUP
        DIRECTION
        PROXIMITY
    Ignore all others — LSS only cares about location-aware context.
    """
    relevant = []
    for ent in tokens.doc.ents:
        if ent.start >= tokens.start and ent.end <= tokens.end:
            if ent.label_ in {"LOCALE", "REGION", "GROUP", "DIRECTION", "PROXIMITY"}:
                relevant.append(ent)
    return sorted(relevant, key=lambda s: s.start)


# ---------------------------------------------------------------------------
# Location Construction
# ---------------------------------------------------------------------------

def _build_location_objects(spans: List[Span]) -> List[Location]:
    """
    Convert LOCALE-tagged spans into preliminary Location objects.
    No Gazetteer resolution happens here; DOM handles candidate generation.
    """
    locs: List[Location] = []

    for sp in spans:
        if sp.label_ == "LOCALE":
            loc = Location(
                text=sp.text,
                candidates=[],        # DOM will fill this later
                selection=None,
                selection_confidence=0.0,
                cluster_id=None,
                contexts=[],
                span=sp,              # user added this field
            )
            locs.append(loc)

    return locs


# ---------------------------------------------------------------------------
# Actor Extraction
# ---------------------------------------------------------------------------

def _extract_actor(spans: List[Span]) -> Optional[Actor]:
    """
    Heuristics:
    - GROUP spans are the strongest actor signals
    - UNIT spans could be added later when ruler defines them
    """
    for sp in spans:
        if sp.label_ == "GROUP":
            return Actor(kind=ActorKind.GROUP, text=sp.text)
    return None


# ---------------------------------------------------------------------------
# Action Extraction (Holmes)
# ---------------------------------------------------------------------------

def _extract_action(hem: EventMatch) -> Optional[Action]:
    """
    Holmes already provides the governing verb in search_phrase_text.
    We classify it using rough heuristics.
    """

    verb = hem.search_phrase_text.lower().strip()
    if not verb:
        return None

    # Naive classification; DOM or action taxonomy layer handles refinements later.
    if "shell" in verb:
        return Action(kind=ActionKind.SHELLING, label="artillery_shelling", text=verb)
    if verb in {"attack", "attacked", "assault"}:
        return Action(kind=ActionKind.ATTACK, label="attack", text=verb)
    if verb in {"advance", "advanced"}:
        return Action(kind=ActionKind.ADVANCE, label="advance", text=verb)
    if verb in {"defend", "defended"}:
        return Action(kind=ActionKind.DEFENSE, label="defense", text=verb)
    if verb in {"capture", "captured", "took"}:
        return Action(kind=ActionKind.CAPTURE, label="capture", text=verb)

    return Action(kind=ActionKind.OTHER, label="other", text=verb)


# ---------------------------------------------------------------------------
# Context Assignment: Core Logic
# ---------------------------------------------------------------------------

def _assign_context_to_locations_and_event(
    spans: List[Span],
    locations: List[Location],
    event_contexts: List[SitRepContext],
):
    """
    This implements the scoping strategy:

        • Parenthetical contexts after location series
        • Preposed region/direction/group/proximity
        • Veiled contexts (“near X”, “in the Kupyansk direction”)
        • Determine whether context is location-specific or event-wide

    DOM layer will later interpret and filter by context.value.
    """

    # Helper: find Location objects by token index
    def locs_in_range(start: int, end: int) -> List[Location]:
        out = []
        for loc in locations:
            if loc.span.start >= start and loc.span.end <= end:
                out.append(loc)
        return out

    # Pass 1: detect parenthetical context that follows location sequences
    for sp in spans:
        if sp.label_ not in {"REGION", "DIRECTION", "PROXIMITY", "GROUP"}:
            continue

        # Pattern: "A, B, C (REGION)" or "A, B in X REGION"
        prev_locs = _collect_preceding_locations(spans, locations, sp)

        if prev_locs:
            ctx = SitRepContext(
                kind=_ctx_kind_for_label(sp.label_),
                value=sp.text,
                text=sp.text,
                location_id=None,
                event_id=None,
            )

            for loc in prev_locs:
                loc.contexts.append(ctx)
            continue

        # If no preceding locations -> context is event-wide
        event_contexts.append(
            SitRepContext(
                kind=_ctx_kind_for_label(sp.label_),
                value=sp.text,
                text=sp.text,
            )
        )

    # Pass 2: detect veiled contexts — “near X” or “in the Kupyansk direction”
    _handle_veiled_contexts(spans, locations, event_contexts)


# ---------------------------------------------------------------------------
# Veiled Contexts
# ---------------------------------------------------------------------------

def _handle_veiled_contexts(spans, locations, event_contexts):
    """
    Handles:
        - "near LOCATION" → PROXIMITY for that location
        - "in the Kupyansk direction" → DIRECTION, usually event-wide unless tightly bound
    """

    for sp in spans:
        if sp.label_ == "DIRECTION":
            # If the direction precedes all location mentions → event-level
            if all(loc.span.start > sp.start for loc in locations):
                event_contexts.append(
                    SitRepContext(
                        kind=CtxKind.DIRECTION,
                        value=sp.text,
                        text=sp.text,
                    )
                )
            else:
                # Attach to the nearest location after the direction phrase
                loc = _nearest_location_after(sp, locations)
                if loc:
                    loc.contexts.append(
                        SitRepContext(
                            kind=CtxKind.DIRECTION,
                            value=sp.text,
                            text=sp.text,
                        )
                    )
                else:
                    event_contexts.append(
                        SitRepContext(
                            kind=CtxKind.DIRECTION,
                            value=sp.text,
                            text=sp.text,
                        )
                    )

        elif sp.label_ == "PROXIMITY":
            # Always local if tied syntactically
            loc = _nearest_location_after(sp, locations)
            if loc:
                loc.contexts.append(
                    SitRepContext(
                        kind=CtxKind.PROXIMITY,
                        value=sp.text,
                        text=sp.text,
                    )
                )
            else:
                event_contexts.append(
                    SitRepContext(
                        kind=CtxKind.PROXIMITY,
                        value=sp.text,
                        text=sp.text,
                    )
                )


# ---------------------------------------------------------------------------
# Helper Utilities
# ---------------------------------------------------------------------------

def _nearest_location_after(span: Span, locations: List[Location]) -> Optional[Location]:
    after = [loc for loc in locations if loc.span.start > span.start]
    if not after:
        return None
    return min(after, key=lambda l: l.span.start)


def _collect_preceding_locations(spans: List[Span], locations: List[Location], ctx_span: Span) -> List[Location]:
    """
    Returns ALL consecutive locations directly before a context phrase,
    respecting punctuation boundaries.
    """
    preceding = []
    for loc in reversed(locations):
        if loc.span.end <= ctx_span.start:
            preceding.append(loc)
        else:
            break
    return list(reversed(preceding))


def _ctx_kind_for_label(label: str) -> CtxKind:
    return {
        "REGION": CtxKind.REGION,
        "DIRECTION": CtxKind.DIRECTION,
        "GROUP": CtxKind.GROUP,
        "PROXIMITY": CtxKind.PROXIMITY,
    }.get(label, CtxKind.PROXIMITY)
