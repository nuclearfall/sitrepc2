# src/sitrepc2/lss/pipeline.py

from __future__ import annotations

from collections import defaultdict
from typing import Sequence, Optional

from spacy.tokens import Doc
from holmes_extractor import Manager

from sitrepc2.lss.bootstrap import build_manager
from sitrepc2.lss.phrases import register_search_phrases
from sitrepc2.lss.ruler import add_entity_rulers_from_db
from sitrepc2.lss.sectioning import split_into_sections
from sitrepc2.lss.events import (
    build_word_matches,
    compute_doc_span_from_raw_word_matches,
)
from sitrepc2.lss.lss_scoping import lss_scope_event
from sitrepc2.lss.persist import (
    create_lss_run,
    complete_lss_run,
    persist_section,
    persist_event,
    persist_role_candidate,
    persist_context_span,
)
from sitrepc2.lss.typedefs import EventMatch
"""
LSS PIPELINE (FINAL)

This pipeline is contract-stable.
Downstream layers (DOM, review, audit) MUST NOT
reinterpret raw text or Holmes output directly.

All semantic interpretation begins from lss_* tables.
"""


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
    ingest_posts: Sequence[dict],
    *,
    manager: Optional[Manager] = None,
    batch_size: int = 8,
    min_similarity: float = 0.0,
) -> None:
    """
    Execute the LSS layer and persist unresolved, reviewable outputs.

    This function:
      • does NOT return objects
      • does NOT assume in-memory continuity
      • writes ONLY LSS tables
    """

    if manager is None:
        manager = build_holmes_and_nlp()

    nlp = manager.nlp

    # -------------------------------------------------------------
    # Prepare documents
    # -------------------------------------------------------------

    post_ids = [p["id"] for p in ingest_posts]
    texts = [p["text"] for p in ingest_posts]

    docs: dict[int, Doc] = {}

    for pid, doc in zip(post_ids, nlp.pipe(texts, batch_size=batch_size)):
        docs[pid] = doc

    manager.register_serialized_documents(
        {str(pid): doc.to_bytes() for pid, doc in docs.items()}
    )

    raw_matches = manager.match()
    matches_by_post: dict[int, list[dict]] = defaultdict(list)

    for m in raw_matches:
        label = m.get("document") or m.get("document_label")
        if label is not None:
            matches_by_post[int(label)].append(m)

    # -------------------------------------------------------------
    # Per-post LSS execution
    # -------------------------------------------------------------

    for post in ingest_posts:
        ingest_post_id = post["id"]
        doc = docs[ingest_post_id]

        lss_run_id = create_lss_run(
            ingest_post_id=ingest_post_id,
            engine="holmes",
            engine_version=None,
            model=nlp.meta.get("name"),
        )

        # -------------------------
        # Sections
        # -------------------------

        sections = split_into_sections(post["text"])

        section_id_by_ordinal: dict[int, int] = {}

        for sec in sections:
            section_db_id = persist_section(
                lss_run_id=lss_run_id,
                ingest_post_id=ingest_post_id,
                text=sec.text,
                ordinal=sec.position,
            )
            section_id_by_ordinal[sec.position] = section_db_id

        # -------------------------
        # Events
        # -------------------------

        for ordinal, raw in enumerate(matches_by_post.get(ingest_post_id, [])):
            similarity = float(raw.get("overall_similarity_measure", 1.0))
            if similarity < min_similarity:
                continue

            start, end = compute_doc_span_from_raw_word_matches(raw)
            text = raw.get("sentences_within_document") or doc[start:end].text

            word_matches = build_word_matches(raw)

            event = EventMatch(
                event_id=f"{ingest_post_id}:{ordinal}",
                post_id=str(ingest_post_id),
                label=raw.get("label", ""),
                search_phrase_text=raw.get("search_phrase_text", ""),
                sentences_within_document=text,
                overall_similarity=similarity,
                negated=bool(raw.get("negated", False)),
                uncertain=bool(raw.get("uncertain", False)),
                involves_coreference=bool(raw.get("involves_coreference", False)),
                doc_start_token_index=start,
                doc_end_token_index=end,
                word_matches=word_matches,
                raw_match=raw,
            )

            # Section binding is positional only
            section_id = section_id_by_ordinal.get(0)

            lss_event_id = persist_event(
                lss_run_id=lss_run_id,
                ingest_post_id=ingest_post_id,
                section_id=section_id,
                event_uid=event.event_id,
                label=event.label,
                search_phrase=event.search_phrase_text,
                text=text,
                start_token=start,
                end_token=end,
                ordinal=ordinal,
                similarity=event.overall_similarity,
                negated=event.negated,
                uncertain=event.uncertain,
                involves_coreference=event.involves_coreference,
            )

            # -------------------------
            # LSS scoping
            # -------------------------

            role_candidates, context_spans = lss_scope_event(
                doc=doc,
                event=event,
            )

            for rc in role_candidates:
                persist_role_candidate(
                    lss_event_id=lss_event_id,
                    role_kind=rc.role_kind,
                    document_word=rc.text,
                    document_phrase=None,
                    start_token=rc.start_token,
                    end_token=rc.end_token,
                    match_type=None,
                    negated=rc.negated,
                    uncertain=rc.uncertain,
                    involves_coreference=rc.involves_coreference,
                    similarity=rc.similarity,
                    explanation=rc.explanation,
                )

            for ctx in context_spans:
                persist_context_span(
                    lss_run_id=lss_run_id,
                    ingest_post_id=ingest_post_id,
                    ctx_kind=ctx.ctx_kind,
                    text=ctx.text,
                    start_token=ctx.start_token,
                    end_token=ctx.end_token,
                )

        complete_lss_run(lss_run_id)
