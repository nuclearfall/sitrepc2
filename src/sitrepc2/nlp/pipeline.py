# src/sitrepc2/nlp/pipeline.py
from __future__ import annotations

from collections import defaultdict
from typing import Sequence, Any
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spacy.tokens import Doc

from sitrepc2.nlp import add_gazetteer_ruler, OtherEntitySpec  # wherever you put this
from sitrepc2.holmes.bootstrap import build_manager  # returns a Manager with .nlp
from sitrepc2.holmes.phrases import register_war_search_phrases
from sitrepc2.holmes.events import (
    HolmesEventMatch,
    _build_word_matches,
    _compute_doc_span_from_raw_word_matches,
)
from .typedefs import WarEvent


def build_holmes_and_nlp(
    other_entity: OtherEntitySpec | None = None,
    ) -> Manager:

    # 1) Build manager, add ruler, and register war search phrases
    manager = build_manager()
    manager.nlp = add_gazetteer_ruler(manager.nlp, other_entity)
    # This now automatically takes lexicon from config
    register_war_search_phrases(manager)

    return manager


def run_holmes_over_posts(
    posts: Sequence[object],
    manager: Manager | None = None,
    *,
    batch_size: int = 8,  # don't exceed 10 without a GPU
    min_similarity: float = 0.0,
    other_entity: OtherEntitySpec | None = None,
) -> dict[str, list[WarEvent]]:
    """
    End-to-end:
      posts -> batched nlp.pipe -> docs registered in Holmes -> matches -> WarEvents per post_id.
    """
    # 1) If we're not provided a manager, create a new one.
    if manager is None:
        manager = build_holmes_and_nlp(other_entity)

    nlp = manager.nlp  # use the same nlp Holmes is configured with

    # 2) Parse all posts in batches via nlp.pipe
    post_ids = [getattr(p, "post_id", str(i)) for i, p in enumerate(posts)]
    texts = [p.text for p in posts]

    docs_by_post_id: dict[str, "Doc"] = {}

    for post_id, doc in zip(post_ids, nlp.pipe(texts, batch_size=batch_size)):
        docs_by_post_id[post_id] = doc

    # 3) Register serialized docs with Holmes (so it doesn't have to re-parse)
    serialized = {pid: doc.to_bytes() for pid, doc in docs_by_post_id.items()}
    manager.register_serialized_documents(serialized)

    # 4) Run Holmes matching once over all registered docs
    raw_matches = manager.match()  # uses all registered search phrases & docs

    # Group matches by document label (we used post_id as the label above)
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

    # 5) Convert raw matches -> HolmesEventMatch -> WarEvent per post
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

            wm_raw = m.get("word_matches", []) or []
            start_idx, end_idx = _compute_doc_span_from_raw_word_matches(wm_raw)
            word_matches = _build_word_matches(wm_raw)

            hem = HolmesEventMatch(
                event_id=event_id,
                post_id=post_id,
                label=label,
                overall_similarity=overall_similarity,
                negated=negated,
                uncertain=uncertain,
                involves_coreference=involves_coreference,
                doc_start_token_index=start_idx,
                doc_end_token_index=end_idx,
                word_matches=word_matches,
                raw_match=m,  # or None if you want to strip raw
            )
            holmes_events.append(hem)

        war_events = build_war_events_for_post(doc, post_id, holmes_events)
        # per-event location enrichment here
        events_by_post[post_id] = war_events

    return events_by_post


def build_war_events_for_post(
    doc: Doc,
    post_id: str,
    holmes_events: list[HolmesEventMatch],
) -> list[WarEvent]:
    war_events: list[WarEvent] = []
    for hem in holmes_events:
        span = doc[hem.doc_start_token_index : hem.doc_end_token_index]
        war_events.append(
            WarEvent(
                event_id=hem.event_id,
                post_id=hem.post_id,
                label=hem.label,
                text=span.text,
                negated=hem.negated,
                uncertain=hem.uncertain,
                involves_coreference=hem.involves_coreference,
                overall_similarity=hem.overall_similarity,
                holmes_match=hem,
                locations=[],  # still empty here
            )
        )
    return war_events
