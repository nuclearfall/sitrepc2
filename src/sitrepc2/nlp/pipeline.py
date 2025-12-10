# ---------------------------------------------------------------------------
# sitrepc2.nlp.pipeline
# ---------------------------------------------------------------------------

from __future__ import annotations

from collections import defaultdict
from typing import Sequence, Dict, List
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spacy.tokens import Doc
    from holmes_extractor import Manager
 
from sitrepc2.events.typedefs import Post, Section, Event
from sitrepc2.nlp.typedefs import EventMatch
from sitrepc2.nlp.sectioning import split_into_sections
from sitrepc2.nlp.context import (   
    extract_post_contexts,
    extract_section_contexts
)
from sitrepc2.nlp.events import (
    build_word_matches,
    compute_doc_span_from_raw_word_matches,
)
from sitrepc2.nlp.ruler import add_entity_ruler
from sitrepc2.nlp.lss_scoping import lss_scope_event
from sitrepc2.nlp.bootstrap import build_manager
from sitrepc2.nlp.phrases import register_search_phrases


# ===========================================================================
# MANAGER + NLP INITIALIZATION
# ===========================================================================

def build_holmes_and_nlp() -> Manager:
    """
    Constructs the Holmes Manager with entity ruler and search phrases.
    """
    manager = build_manager()
    manager.nlp = add_entity_ruler(manager.nlp)
    register_search_phrases(manager)
    return manager


# ===========================================================================
# TOP-LEVEL PIPELINE ENTRY
# ===========================================================================

def run_nlp_pipeline(
    posts: Sequence[Post],
    manager: Manager | None = None,
    *,
    batch_size: int = 8,
    min_similarity: float = 0.0,
) -> Dict[str, Post]:
    """
    Full NLP pipeline.
    
    Input:
        posts: Sequence[Post]
    Output:
        dict[post_id, Post] where each Post contains:
            • post.contexts
            • post.sections[]
                • section.contexts
                • section.events[]
    """

    # Initialize manager
    if manager is None:
        manager = build_holmes_and_nlp()

    nlp = manager.nlp

    # --------------------------------------------------------------
    # Run spaCy on all posts
    # --------------------------------------------------------------

    post_ids = [p.post_id for p in posts]
    texts = [p.text for p in posts]

    docs_by_post_id: dict[str, Doc] = {}

    for post_id, doc in zip(post_ids, nlp.pipe(texts, batch_size=batch_size)):
        docs_by_post_id[post_id] = doc

    # Register documents in Holmes
    serialized_docs = {pid: doc.to_bytes() for pid, doc in docs_by_post_id.items()}
    manager.register_serialized_documents(serialized_docs)

    # Run Holmes
    raw_matches = manager.match()

    # Bucket matches by post
    matches_by_post: dict[str, list[dict]] = defaultdict(list)
    for m in raw_matches:
        doc_label = (
            m.get("document")
            or m.get("document_label")
            or m.get("document_name")
        )
        if not doc_label:
            raise ValueError("Holmes match missing document label")
        matches_by_post[doc_label].append(m)

    # Build Post → Section → Event structure
    out: Dict[str, Post] = {}

    for post in posts:
        post_id = post.post_id
        doc = docs_by_post_id[post_id]
        raw_for_post = matches_by_post.get(post_id, [])

        # Extract EventMatch dataclasses
        holmes_events: List[EventMatch] = []
        for idx, m in enumerate(raw_for_post):
            overall_similarity = float(m.get("overall_similarity_measure", 1.0))
            if overall_similarity < min_similarity:
                continue

            start_idx, end_idx = compute_doc_span_from_raw_word_matches(m)
            word_matches = build_word_matches(m)

            hem = EventMatch(
                event_id=f"{post_id}:{idx}",
                post_id=post_id,
                label=m.get("search_phrase_label", ""),
                search_phrase_text=str(m.get("search_phrase_text", "") or ""),
                sentences_within_document=str(m.get("sentences_within_document", "") or ""),
                overall_similarity=overall_similarity,
                negated=bool(m.get("negated", False)),
                uncertain=bool(m.get("uncertain", False)),
                involves_coreference=bool(m.get("involves_coreference", False)),
                doc_start_token_index=start_idx,
                doc_end_token_index=end_idx,
                word_matches=word_matches,
                raw_match=m,
            )
            holmes_events.append(hem)

        # ===================================================================
        # 1. SECTION SPLITTING
        # ===================================================================
        sections = split_into_sections(post.text, doc)
        post.sections = sections

        # ===================================================================
        # 2. POST-LEVEL CONTEXT EXTRACTION
        # ===================================================================
        extract_post_contexts(post, doc)

        # ===================================================================
        # 3. SECTION-LEVEL CONTEXT EXTRACTION
        # ===================================================================
        for section in post.sections:
            extract_section_contexts(section, doc)

        # ===================================================================
        # 4. EVENT EXTRACTION + LSS SCOPING
        # ===================================================================
        for hem in holmes_events:
            _place_event_into_structure(doc, post, hem)

        out[post_id] = post

    return out


# ===========================================================================
# EVENT → SECTION ASSIGNMENT
# ===========================================================================

def _place_event_into_structure(doc: Doc, post: Post, hem: EventMatch):
    """
    Uses LSS to build Event, then assigns it into the correct Section.
    """

    # Determine readable text for Event
    if hem.sentences_within_document:
        text = hem.sentences_within_document
    else:
        text = doc[hem.doc_start_token_index : hem.doc_end_token_index].text

    # Call LSS Scoping
    locations, event_contexts, actor, action = lss_scope_event(doc, hem)

    # Build Event dataclass
    event = Event(
        event_id=hem.event_id,
        post_id=post.post_id,
        text=text,
        actor=actor,
        action=action,
        locations=locations,
        contexts=event_contexts,
        negated=hem.negated,
        uncertain=hem.uncertain,
        involves_coreference=hem.involves_coreference,
    )

    event_start_char = doc[hem.doc_start_token_index].idx

    # Find correct Section
    assigned = False
    for section in post.sections:
        sec_start = post.text.find(section.text)
        sec_end = sec_start + len(section.text)

        if sec_start <= event_start_char <= sec_end:
            section.events.append(event)
            assigned = True
            break

    if not assigned:
        # fallback: put into first section
        if post.sections:
            post.sections[0].events.append(event)

    # Optionally push flat event list
    post.events.append(event)
