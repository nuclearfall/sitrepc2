from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Literal

from spacy.tokens import Doc, Span

from sitrepc2.holmes.events import HolmesEventMatch
from sitrepc2.nlp.typedefs import EventLocationMention, LocationKind

LocationLabel = Literal["LOCALE", "REGION"]


def iter_locale_region_spans_for_event(
    doc: Doc,
    hem: HolmesEventMatch,
    *,
    labels: Iterable[LocationLabel] = ("LOCALE", "REGION"),
    require_contained: bool = True,
) -> Iterator[Span]:
    """
    Non-coref path: LOCALE/REGION entities inside the event span.
    """
    event_start = hem.doc_start_token_index
    event_end = hem.doc_end_token_index  # exclusive
    labels_set = set(labels)

    for ent in doc.ents:
        if ent.label_ not in labels_set:
            continue

        if require_contained:
            if ent.start >= event_start and ent.end <= event_end:
                yield ent
        else:
            if ent.start < event_end and ent.end > event_start:
                yield ent


def iter_extracted_locale_region_spans_for_event(
    doc: Doc,
    hem: HolmesEventMatch,
    *,
    labels: Iterable[LocationLabel] = ("LOCALE", "REGION"),
) -> Iterator[Span]:
    """
    Coref/ontology path: use word_match.extracted_word.

    For each word_match with a non-empty 'extracted_word', find LOCALE/REGION
    entities whose surface text contains that string.
    """
    labels_set = set(labels)
    seen: set[tuple[int, int, str]] = set()

    # Build a quick list of candidate location ents
    loc_ents = [ent for ent in doc.ents if ent.label_ in labels_set]

    for wm in hem.word_matches:
        if not wm.extracted_word:
            continue
        needle = wm.extracted_word.lower()

        for ent in loc_ents:
            hay = ent.text.lower()
            # You can tighten this to == if you want, but substring is often safer
            if needle in hay:
                key = (ent.start, ent.end, ent.label_)
                if key in seen:
                    continue
                seen.add(key)
                yield ent


def _span_location_kind(ent: Span) -> LocationKind:
    if ent.label_ == "LOCALE":
        return LocationKind.LOCALE
    if ent.label_ == "REGION":
        return LocationKind.REGION
    raise ValueError(f"Unsupported location entity label: {ent.label_!r}")


def resolve_event_locations(
    doc: Doc,
    hem: HolmesEventMatch,
    *,
    default_role: str = "TARGET",
) -> list[EventLocationMention]:
    """
    Resolve locations for an event using:
      * LOCALE/REGION ents inside the event span
      * LOCALE/REGION ents identified by Holmes via word_match.extracted_word
    """
    mentions: list[EventLocationMention] = []
    seen: set[tuple[int, int, str]] = set()

    # 1) direct in-span mentions
    for ent in iter_locale_region_spans_for_event(doc, hem):
        key = (ent.start, ent.end, ent.label_)
        if key in seen:
            continue
        seen.add(key)

        kind = _span_location_kind(ent)
        mentions.append(
            EventLocationMention(
                mention_id=f"{hem.event_id}:loc{len(mentions)}",
                event_id=hem.event_id,
                role=default_role,
                surface=ent.text,
                span_start=ent.start,
                span_end=ent.end,
                kind=kind,
            )
        )

    # 2) coref/ontology-derived mentions via extracted_word
    for ent in iter_extracted_locale_region_spans_for_event(doc, hem):
        key = (ent.start, ent.end, ent.label_)
        if key in seen:
            continue
        seen.add(key)

        kind = _span_location_kind(ent)
        mentions.append(
            EventLocationMention(
                mention_id=f"{hem.event_id}:loc{len(mentions)}",
                event_id=hem.event_id,
                role=default_role,  # or "COREF_TARGET" if you want to distinguish
                surface=ent.text,
                span_start=ent.start,
                span_end=ent.end,
                kind=kind,
            )
        )

    return mentions
