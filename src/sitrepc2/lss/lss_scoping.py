# src/sitrepc2/lss/lss_scoping.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from spacy.tokens import Doc, Span

from sitrepc2.lss.typedefs import EventMatch, WordMatch


# ---------------------------------------------------------------------
# LSS output data contracts (pure, persistence-ready)
# ---------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class LSSRoleCandidate:
    """
    Unresolved role-bearing span detected by LSS.
    Resolution is deferred to DOM.
    """
    role_kind: str                 # ACTOR / ACTION / LOCATION
    text: str

    start_token: int
    end_token: int

    negated: bool
    uncertain: bool
    involves_coreference: bool
    similarity: float | None

    explanation: str | None = None


@dataclass(frozen=True, slots=True)
class LSSContextSpan:
    """
    Contextual span detected by LSS that is not bound to a specific event.
    """
    ctx_kind: str                  # LOCATION / REGION / GROUP / DIRECTION
    text: str

    start_token: int
    end_token: int


# ---------------------------------------------------------------------
# Canonical gazetteer-backed entity labels
# ---------------------------------------------------------------------

CUSTOM_ENTITY_LABELS = {
    "LOCATION",
    "REGION",
    "GROUP",
    "DIRECTION",
}


# ---------------------------------------------------------------------
# Top-level API
# ---------------------------------------------------------------------

def lss_scope_event(
    *,
    doc: Doc,
    event: EventMatch,
) -> tuple[list[LSSRoleCandidate], list[LSSContextSpan]]:
    """
    Perform LSS scoping for a single event.

    Responsibilities:
    - Extract role candidates from Holmes WordMatches
    - Extract context spans from gazetteer-backed entities only

    No semantic inference is performed here.
    """
    event_span = doc[event.doc_start_token_index : event.doc_end_token_index]

    role_candidates: list[LSSRoleCandidate] = []
    context_spans: list[LSSContextSpan] = []

    # -------------------------------------------------
    # Role candidates from Holmes WordMatches
    # -------------------------------------------------

    for wm in event.iter_content_words():
        role_kind = _infer_role_kind_from_word_match(wm)
        if role_kind is None:
            continue

        role_candidates.append(
            LSSRoleCandidate(
                role_kind=role_kind,
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
    # Context spans from gazetteer-backed entities only
    # -------------------------------------------------

    for ent in doc.ents:
        # Only consider canonical gazetteer entities
        if ent.label_ not in CUSTOM_ENTITY_LABELS:
            continue

        # Only consider entities overlapping the event span
        if not _spans_overlap(
            ent.start, ent.end,
            event_span.start, event_span.end,
        ):
            continue

        context_spans.append(
            LSSContextSpan(
                ctx_kind=ent.label_,
                text=ent.text,
                start_token=ent.start,
                end_token=ent.end,
            )
        )

    return role_candidates, context_spans


# ---------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------

def _spans_overlap(
    start1: int,
    end1: int,
    start2: int,
    end2: int,
) -> bool:
    """
    Check whether two token spans overlap.
    """
    return not (end1 <= start2 or end2 <= start1)


# ---------------------------------------------------------------------
# Role inference helpers (structural only)
# ---------------------------------------------------------------------

def _infer_role_kind_from_word_match(wm: WordMatch) -> str | None:
    """
    Infer a coarse role kind from a WordMatch.

    Structural inference only.
    DOM is responsible for validation and resolution.
    """
    mt = (wm.match_type or "").lower()

    # Actor-like grammatical roles
    if mt in {"subject", "actor", "object", "dobj", "possessor"}:
        return "ACTOR"

    # Action-like roles
    if mt in {"verb", "action"}:
        return "ACTION"

    # Fallback: Holmes extracted a different surface form
    if (
        wm.extracted_word
        and wm.extracted_word.lower() != wm.document_word.lower()
    ):
        return "LOCATION"

    return None
