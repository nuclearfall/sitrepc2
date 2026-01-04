# src/sitrepc2/lss/pipeline.py

from __future__ import annotations

from collections import defaultdict
from typing import Sequence, Optional

import sqlite3
from spacy.tokens import Doc
from holmes_extractor import Manager

from sitrepc2.config.paths import records_path as records_db_path
from sitrepc2.lss.bootstrap import build_manager
from sitrepc2.lss.phrases import register_search_phrases
from sitrepc2.lss.ruler import add_entity_rulers_from_db
from sitrepc2.lss.sectioning import split_into_sections
from sitrepc2.lss.events import (
    compute_doc_span_from_phrase_match,
    build_lss_events,
)
from sitrepc2.lss.persist import (
    create_lss_run,
    complete_lss_run,
    persist_section,
    persist_event,
    persist_role_candidate,
    persist_location_series,
    persist_context_hint,
)
from sitrepc2.lss.typedefs import EventMatch
from sitrepc2.lss.contextualize import contextualize
from sitrepc2.lss.lss_scoping import LSSContextHint


# ---------------------------------------------------------------------
# NLP INITIALIZATION
# ---------------------------------------------------------------------

def build_holmes_and_nlp() -> Manager:
    manager = build_manager()
    manager.nlp = add_entity_rulers_from_db(manager.nlp)
    register_search_phrases(manager)
    return manager


# ---------------------------------------------------------------------
# LSS PIPELINE
# ---------------------------------------------------------------------

def run_lss_pipeline(
    ingest_posts: Sequence[dict],
    *,
    manager: Optional[Manager] = None,
    batch_size: int = 8,
    min_similarity: float = 0.0,
    reprocess: bool = False,
    keep_nonspatial: bool = True,
) -> None:
    if not ingest_posts:
        return

    # -------------------------------------------------------------
    # Incremental execution guard
    # -------------------------------------------------------------

    if not reprocess:
        ingest_ids = [p["id"] for p in ingest_posts]

        with sqlite3.connect(records_db_path()) as con:
            con.execute("PRAGMA foreign_keys = ON;")
            rows = con.execute(
                f"""
                SELECT DISTINCT ingest_post_id
                FROM lss_runs
                WHERE completed_at IS NOT NULL
                  AND ingest_post_id IN ({",".join("?" for _ in ingest_ids)})
                """,
                ingest_ids,
            ).fetchall()

        completed_ids = {row[0] for row in rows}
        ingest_posts = [p for p in ingest_posts if p["id"] not in completed_ids]

        if not ingest_posts:
            return

    # -------------------------------------------------------------
    # NLP / Holmes setup
    # -------------------------------------------------------------

    if manager is None:
        manager = build_holmes_and_nlp()

    nlp = manager.nlp

    docs: dict[int, Doc] = {}
    for pid, doc in zip(
        (p["id"] for p in ingest_posts),
        nlp.pipe((p["text"] for p in ingest_posts), batch_size=batch_size),
    ):
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
    # Per-post execution
    # -------------------------------------------------------------

    for post in ingest_posts:
        ingest_post_id = post["id"]
        doc = docs.get(ingest_post_id)
        if doc is None:
            continue

        lss_run_id: Optional[int] = None

        try:
            lss_run_id = create_lss_run(
                ingest_post_id=ingest_post_id,
                engine="holmes",
                model=nlp.meta.get("name"),
            )

            event_matches: list[EventMatch] = []
            context_hints: list[LSSContextHint] = []

            event_ordinal = 0

            # -------------------------
            # DISAMBIGUATION POINT
            # -------------------------

            for raw in matches_by_post.get(ingest_post_id, []):
                label = raw.get("search_phrase_label", "")

                if label.startswith("EVENT:"):
                    similarity = float(raw.get("overall_similarity_measure", 1.0))
                    if similarity < min_similarity:
                        continue

                    start, end = compute_doc_span_from_phrase_match(raw)
                    text = raw.get("sentences_within_document") or doc[start:end].text

                    event_matches.append(
                        EventMatch(
                            event_id=f"{ingest_post_id}:{event_ordinal}",
                            post_id=str(ingest_post_id),
                            label=label,
                            search_phrase_text=raw.get("search_phrase_text", ""),
                            sentences_within_document=text,
                            overall_similarity=similarity,
                            negated=bool(raw.get("negated", False)),
                            uncertain=bool(raw.get("uncertain", False)),
                            involves_coreference=bool(raw.get("involves_coreference", False)),
                            doc_start_token_index=start,
                            doc_end_token_index=end,
                            raw_match=raw,
                        )
                    )
                    event_ordinal += 1

                elif label.startswith("CONTEXT:"):
                    context_hints.append(
                        LSSContextHint.from_holmes_match(
                            raw=raw,
                            doc=doc,
                        )
                    )

            # -------------------------
            # Structural scoping
            # -------------------------

            lss_events, rejected_nonspatial = build_lss_events(
                doc=doc,
                event_matches=event_matches,
                collect_nonspatial=keep_nonspatial,
            )

            # -------------------------
            # Sections
            # -------------------------

            sections = split_into_sections(post["text"])
            section_id_by_ordinal: dict[int, int] = {}

            for sec in sections:
                if sec.ordinal == 0:
                    section_id_by_ordinal[0] = persist_section(
                        lss_run_id=lss_run_id,
                        ingest_post_id=ingest_post_id,
                        text=sec.text,
                        ordinal=sec.ordinal,
                    )

            if not lss_events:
                complete_lss_run(lss_run_id)
                continue

            # -------------------------
            # Context lattice
            # -------------------------

            section_ordinals = sorted(section_id_by_ordinal.keys())
            event_ordinals_by_section = {0: list(range(len(lss_events)))}

            for idx, (event, roles, series_list, _) in enumerate(lss_events):
                lss_events[idx] = (
                    event,
                    roles,
                    series_list,
                    contextualize(
                        context_hints=context_hints,
                        section_ordinals=section_ordinals,
                        event_ordinals_by_section=event_ordinals_by_section,
                    ),
                )

            # -------------------------
            # Persistence
            # -------------------------

            event_id_map: dict[int, int] = {}

            for ordinal, (event, roles, series_list, hints) in enumerate(lss_events):
                section_id = section_id_by_ordinal.get(0)

                lss_event_id = persist_event(
                    lss_run_id=lss_run_id,
                    ingest_post_id=ingest_post_id,
                    section_id=section_id,
                    event_uid=event.event_id,
                    label=event.label,
                    search_phrase=event.search_phrase_text,
                    text=event.sentences_within_document,
                    start_token=event.doc_start_token_index,
                    end_token=event.doc_end_token_index,
                    ordinal=ordinal,
                    similarity=event.overall_similarity,
                    negated=event.negated,
                    uncertain=event.uncertain,
                    involves_coreference=event.involves_coreference,
                )

                event_id_map[ordinal] = lss_event_id

                for rc in roles:
                    persist_role_candidate(lss_event_id=lss_event_id, rc=rc)

                series_id_map = {}
                item_id_map = {}

                for series in series_list:
                    mapping = persist_location_series(
                        lss_event_id=lss_event_id,
                        series=series,
                    )
                    series_id_map[series.series_id] = list(mapping.values())[0]
                    item_id_map.update(mapping)

                for hint in hints:
                    persist_context_hint(
                        lss_run_id=lss_run_id,
                        hint=hint,
                        series_id_map=series_id_map,
                        item_id_map=item_id_map,
                        event_id_map=event_id_map,
                        section_id_map=section_id_by_ordinal,
                    )

            complete_lss_run(lss_run_id)

        except Exception:
            raise
