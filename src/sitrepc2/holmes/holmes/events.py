# src/sitrepc2/holmes/events.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, List

import holmes_extractor as holmes


@dataclass(frozen=True, slots=True)
class HolmesWordMatch:
    search_phrase_word: str
    document_word: str
    document_token_index: int

    match_type: str
    negated: bool
    uncertain: bool
    involves_coreference: bool


@dataclass(frozen=True, slots=True)
class HolmesEventMatch:
    event_id: str
    post_id: str

    label: str
    overall_similarity: float

    negated: bool
    uncertain: bool
    involves_coreference: bool

    doc_start_token_index: int
    doc_end_token_index: int

    word_matches: list[HolmesWordMatch]
    raw_match: dict[str, Any] | None = None

    def iter_content_words(self) -> Iterable[HolmesWordMatch]:
        for wm in self.word_matches:
            if wm.document_word.lower() in {"somebody", "something"}:
                continue
            yield wm
