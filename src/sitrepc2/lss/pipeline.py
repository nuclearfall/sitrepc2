# src/sitrepc2/lss/pipeline.py

from __future__ import annotations

from collections import defaultdict
from typing import Sequence, Optional

from spacy.tokens import Doc
from holmes_extractor import Manager

from sitrepc2.lss.bootstrap import build_manager
from sitrepc2.lss.phrases import register_search_phrases
from sitrepc2.lss.rulers import add_entity_rulers_from_db
from sitrepc2.lss.sectioning import split_into_sections
from sitrepc2.lss.context import (
    extract_post_contexts,
    extract_section_contexts,
)
from sitrepc2.lss.events import compute_doc_span_from_raw_word_matches
from sitrepc2.lss.lss_scoping import lss_scope_event
from sitrepc2.lss.persist import (
    persist_post,
    persist_section,
    persist_event_claim,
    persist_context_hint,
    persist_location_hint,
    persist_actor_hint,
    persist_action_hint,
)
from sitrepc2.lss.ids import make_id


# ---------------------------------------------------------------------
# NLP INITIALIZATION
# ---------------------------------------------------------------------

def build_holmes_and_nlp() -> Manager:
    manager = build_manager()
    manager.nlp = add_entity_rulers_from_db(manager.nlp)
    register_search_phrases(manager)
    return manager


# ---------------------------------------------------------------------
# LSS PIPELINE (WRITE-ONLY, DB-BACKED)
# ---------------------------------------------------------------------

def run_lss_pipeline(
    posts: Sequence[dict],
    *,
    manager: Optional[Manager] = None,
    batch_size: int = 8,
    min_similarity: float = 0.0,
) -> None:
    """
    Executes the LSS layer and persists a fully scoped, reviewable tree
    into the LSS database.

    This function:
      • does NOT return objects
      • does NOT assume in-memory continuity
      • writes everything required for review + DOM
    """

    if manager is None:
        manager = build_holmes_and_nlp()

    nlp = manager.nlp

    # -------------------------------------------------------------
    # 1. Persist raw posts
    # -------------------------------------------------------------

    for post in posts:
        persist_post(post)

    post_ids = [p["post_id"] for p in posts]
    texts = [p["text"] for p in posts]

    docs: dict[str, Doc] = {}

    for pid, doc in zip(post_ids, nlp.pipe(texts, batch_size=batch_size)):
        docs[pid] = doc

    manager.register_serialized_documents(
        {pid: doc.to_bytes() for pid, doc in docs.items()}
    )

    raw_matches = manager.match()
    matches_by_post: dict[str, list[dict]] = defaultdict(list)

    for m in raw_matches:
        label = m.get("document") or m.get("document_label")
        if label:
            matches_by_post[label].append(m)

    # -------------------------------------------------------------
    # 2. Structural build + persistence
    # -------------------------------------------------------------

    for post in posts:
        post_id = post["post_id"]
        doc = docs[post_id]

        # -------------------------
        # Sections
        # -------------------------

        sections = split_into_sections(post["text"], doc)

        for idx, section in enumerate(sections):
            persist_section(
                post_id=post_id,
                section_id=section.section_id,
                position=idx,
                text=section.text,
            )

        # -------------------------
        # Post-level contexts
        # -------------------------

        extract_post_contexts(post, doc)
        for ctx in post.contexts:
            persist_context_hint(
                kind=ctx.kind.value,
                text=ctx.text,
                scope="POST",
                post_id=post_id,
                section_id=None,
                claim_id=None,
                location_id=None,
            )

        # -------------------------
        # Section-level contexts
        # -------------------------

        for section in sections:
            extract_section_contexts(section, doc)
            for ctx in section.contexts:
                persist_context_hint(
                    kind=ctx.kind.value,
                    text=ctx.text,
                    scope="SECTION",
                    post_id=post_id,
                    section_id=section.section_id,
                    claim_id=None,
                    location_id=None,
                )

        # -------------------------
        # Event claims
        # -------------------------

        for idx, raw in enumerate(matches_by_post.get(post_id, [])):
            sim = float(raw.get("overall_similarity_measure", 1.0))
            if sim < min_similarity:
                continue

            start, end = compute_doc_span_from_raw_word_matches(raw)
            text = raw.get("sentences_within_document") or doc[start:end].text

            claim_id = make_id("claim", post_id, str(idx), text)

            # Determine owning section
            section_id = sections[0].section_id
            for section in sections:
                if section.text and section.text in text:
                    section_id = section.section_id
                    break

            persist_event_claim(
                claim_id=claim_id,
                post_id=post_id,
                section_id=section_id,
                text=text,
                negated=bool(raw.get("negated", False)),
                uncertain=bool(raw.get("uncertain", False)),
            )

            # -------------------------------------------------
            # LSS SCOPING (THIS IS THE CRITICAL PART)
            # -------------------------------------------------

            locations, event_contexts, actor, action = lss_scope_event(doc, raw)

            # -------------------------
            # Event-level contexts
            # -------------------------

            for ctx in event_contexts:
                persist_context_hint(
                    kind=ctx.kind.value,
                    text=ctx.text,
                    scope="CLAIM",
                    post_id=post_id,
                    section_id=section_id,
                    claim_id=claim_id,
                    location_id=None,
                )

            # -------------------------
            # Locations + location-scoped contexts
            # -------------------------

            for loc_idx, loc in enumerate(locations):
                location_id = make_id(
                    "location",
                    claim_id,
                    str(loc_idx),
                    loc.text,
                )

                persist_location_hint(
                    claim_id=claim_id,
                    location_id=location_id,
                    text=loc.text,
                    asserted=True,
                )

                for ctx in loc.contexts:
                    persist_context_hint(
                        kind=ctx.kind.value,
                        text=ctx.text,
                        scope="LOCATION",
                        post_id=post_id,
                        section_id=section_id,
                        claim_id=claim_id,
                        location_id=location_id,
                    )

            # -------------------------
            # Actor / Action
            # -------------------------

            if actor:
                persist_actor_hint(
                    claim_id=claim_id,
                    text=actor.text,
                    kind_hint=actor.kind.value,
                )

            if action:
                persist_action_hint(
                    claim_id=claim_id,
                    text=action.text,
                )
