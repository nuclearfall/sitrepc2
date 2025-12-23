from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional


# ============================================================
# HOLMES WORD MATCH (THIN WRAPPER)
# ============================================================

@dataclass(frozen=True, slots=True)
class WordMatch:
    """
    Thin wrapper around one entry from the 'word_matches' list in the
    dictionary returned by Holmes Manager.match().

    This mirrors the documented properties in Holmes 6.7 as far as LSS
    needs them. No interpretation happens here.
    """

    search_phrase_token_index: int
    search_phrase_word: str

    document_token_index: int
    first_document_token_index: int
    last_document_token_index: int
    structurally_matched_document_token_index: int

    document_subword_index: Optional[int]
    document_subword_containing_token_index: Optional[int]

    document_word: str
    document_phrase: str

    match_type: str
    negated: bool
    uncertain: bool
    similarity_measure: float
    involves_coreference: bool

    extracted_word: Optional[str]
    depth: int
    explanation: Optional[str]


# ============================================================
# HOLMES EVENT MATCH (TRANSPORT OBJECT)
# ============================================================

@dataclass(frozen=True, slots=True)
class EventMatch:
    """
    High-level wrapper around a single Holmes match dict.

    This is a *transport object only*:
      • used by LSS to extract spans
      • never stored directly
      • never mutated
      • never passed beyond LSS (except transiently through events.py)

    All persistence happens via derived tables.
    """

    event_id: str
    post_id: str

    label: str
    search_phrase_text: str
    sentences_within_document: str

    overall_similarity: float
    negated: bool
    uncertain: bool
    involves_coreference: bool

    doc_start_token_index: int
    doc_end_token_index: int

    word_matches: list[WordMatch]
    raw_match: Optional[dict[str, Any]] = None

    def iter_content_words(self) -> Iterable[WordMatch]:
        """
        Yield word-matches that are not generic placeholders
        like 'somebody' or 'something'.
        """
        for wm in self.word_matches:
            if wm.document_word.lower() in {"somebody", "something"}:
                continue
            yield wm