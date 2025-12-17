# src/sitrepc2/lss/lss_scoping.py

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from spacy.tokens import Doc

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
    Contextual span detected by LSS that is not bound to a specific role.
    """
    ctx_kind: str                  # REGION / GROUP / DIRECTION / PROXIMITY
    text: str

    start_token: int | None
    end_token: int | None


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

    Returns:
        role_candidates: unresolved ACTOR / ACTION / LOCATION candidates
        context_spans:   unbound contextual spans
    """

    span = doc[event.doc_start_token_index : event.doc_end_token_index]

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
    # Context spans from spaCy entity ruler
    # -------------------------------------------------

    for ent in doc.ents:
        if ent.start < span.start or ent.end > span.end:
            continue

        if ent.label_ not in {
            "REGION",
            "GROUP",
            "DIRECTION",
            "PROXIMITY",
        }:
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
# Role inference helpers (structural only)
# ---------------------------------------------------------------------

def _infer_role_kind_from_word_match(wm: WordMatch) -> str | None:
    """
    Infer a coarse role kind from a WordMatch.

    This is *structural inference only* and may over-generate.
    DOM is responsible for validation and resolution.
    """

    mt = (wm.match_type or "").lower()

    if "actor" in mt or "subject" in mt:
        return "ACTOR"

    if "action" in mt or "verb" in mt:
        return "ACTION"

    # Heuristic fallback: extracted span differs from surface word
    if wm.extracted_word and wm.extracted_word.lower() != wm.document_word.lower():
        return "LOCATION"

    return None
