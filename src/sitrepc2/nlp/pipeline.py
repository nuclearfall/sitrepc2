# src/sitrepc2/nlp/pipeline.py
from __future__ import annotations

from collections import defaultdict
from typing import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spacy.tokens import Doc
    from holmes_extractor import Manager

from sitrepc2.nlp import add_gazetteer_ruler, OtherEntitySpec
from sitrepc2.holmes.bootstrap import build_manager
from sitrepc2.holmes.phrases import register_war_search_phrases
from sitrepc2.holmes.events import (
    HolmesEventMatch,
    build_word_matches,
    compute_doc_span_from_raw_word_matches,
)
from sitrepc2.locations.event_locations import resolve_event_locations
from .typedefs import WarEvent


def build_holmes_and_nlp(
    other_entity: OtherEntitySpec | None = None,
) -> Manager:
    manager = build_manager()
    manager.nlp = add_gazetteer_ruler(manager.nlp, other_entity)
    register_war_search_phrases(manager)
    return manager


def run_holmes_over_posts(
    posts: Sequence[object],
    manager: Manager | None = None,
    *,
    batch_size: int = 8,
    min_similarity: float = 0.0,
    other_entity: OtherEntitySpec | None = None,
) -> dict[str, list[WarEvent]]:
    if manager is None:
        manager = build_holmes_and_nlp(other_entity)

    nlp = manager.nlp

    post_ids = [getattr(p, "post_id", str(i)) for i, p in enumerate(posts)]
    texts = [p.text for p in posts]

    docs_by_post_id: dict[str, Doc] = {}

    for post_id, doc in zip(post_ids, nlp.pipe(texts, batch_size=batch_size)):
        docs_by_post_id[post_id] = doc

    serialized = {pid: doc.to_bytes() for pid, doc in docs_by_post_id.items()}
    manager.register_serialized_documents(serialized)

    raw_matches = manager.match()

    raw_by_post_id: dict[str, list[dict]] = defaultdict(list)
    for m in raw_matches:
        doc_label = (
            m.get("document")
            or m.get("document_label")
            or m.get("document_name")
        )
        if not doc_label:
            raise ValueError(
                f"Holmes match missing document label: keys={list(m.keys())}"
            )
        raw_by_post_id[doc_label].append(m)

    events_by_post: dict[str, list[WarEvent]] = {}

    for post, post_id in zip(posts, post_ids):
        doc = docs_by_post_id[post_id]
        raw_for_post = raw_by_post_id.get(post_id, [])
        holmes_events: list[HolmesEventMatch] = []

        for idx, m in enumerate(raw_for_post):
            overall_similarity = float(m.get("overall_similarity_measure", 1.0))
            if overall_similarity < min_similarity:
                continue

            event_id = f"{post_id}:{idx}"
            label = m.get("search_phrase_label", "")

            negated = bool(m.get("negated", False))
            uncertain = bool(m.get("uncertain", False))
            involves_coreference = bool(m.get("involves_coreference", False))

            search_phrase_text = str(m.get("search_phrase_text", "") or "")
            sentences_within_document = str(
                m.get("sentences_within_document", "") or ""
            )

            start_idx, end_idx = compute_doc_span_from_raw_word_matches(m)
            word_matches = build_word_matches(m)

            hem = HolmesEventMatch(
                event_id=event_id,
                post_id=post_id,
                label=label,
                search_phrase_text=search_phrase_text,
                sentences_within_document=sentences_within_document,
                overall_similarity=overall_similarity,
                negated=negated,
                uncertain=uncertain,
                involves_coreference=involves_coreference,
                doc_start_token_index=start_idx,
                doc_end_token_index=end_idx,
                word_matches=word_matches,
                raw_match=m,
            )
            holmes_events.append(hem)

        war_events = build_war_events_for_post(doc, post_id, holmes_events)
        events_by_post[post_id] = war_events

    return events_by_post


def build_war_events_for_post(
    doc: Doc,
    post_id: str,
    holmes_events: list[HolmesEventMatch],
) -> list[WarEvent]:
    war_events: list[WarEvent] = []

    for hem in holmes_events:
        # Prefer Holmes' own sentence text for human-readable event text.
        # Fallback to doc span if for some reason it is empty.
        if hem.sentences_within_document:
            text = hem.sentences_within_document
        else:
            text = doc[hem.doc_start_token_index : hem.doc_end_token_index].text

        event = WarEvent(
            event_id=hem.event_id,
            post_id=hem.post_id,
            label=hem.label,
            text=text,
            negated=hem.negated,
            uncertain=hem.uncertain,
            involves_coreference=hem.involves_coreference,
            overall_similarity=hem.overall_similarity,
            holmes_match=hem,
            locations=[],
        )

        # Attach EventLocationMention objects (direct + via extracted_word)
        event.locations.extend(resolve_event_locations(doc, hem))

        war_events.append(event)

    return war_events
