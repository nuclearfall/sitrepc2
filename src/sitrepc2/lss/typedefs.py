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

    Transport object only.
    Never persisted.
    Never interpreted.
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

    raw_match: dict[str, Any]

    # -------------------------------
    # Holmes accessors (thin only)
    # -------------------------------

    def iter_word_matches(self) -> Iterable[WordMatch]:
        """
        Yield WordMatch wrappers for Holmes 'word_matches'.
        No filtering. No interpretation.
        """
        for wm in self.raw_match.get("word_matches", []):
            yield WordMatch(**wm)

    def iter_content_words(self) -> Iterable[WordMatch]:
        """
        Yield content-bearing WordMatches only.
        This mirrors Holmes semantics and is still structural.
        """
        for wm in self.iter_word_matches():
            if wm.match_type:
                yield wm