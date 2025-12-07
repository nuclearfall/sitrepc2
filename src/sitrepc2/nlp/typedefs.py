from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class HolmesWordMatch:
    """
    Thin wrapper around one entry from the 'word_matches' list in the
    dictionary returned by Holmes Manager.match().

    This mirrors the documented properties in 6.7 as far as we care
    about them right now.
    """

    search_phrase_token_index: int
    search_phrase_word: str

    document_token_index: int
    first_document_token_index: int
    last_document_token_index: int
    structurally_matched_document_token_index: int

    document_subword_index: int | None
    document_subword_containing_token_index: int | None

    document_word: str
    document_phrase: str

    match_type: str
    negated: bool
    uncertain: bool
    similarity_measure: float
    involves_coreference: bool

    extracted_word: str | None
    depth: int
    explanation: str | None


@dataclass(frozen=True, slots=True)
class HolmesEventMatch:
    """
    High-level wrapper around a single Holmes match dict for structural
    extraction use.

    We store Holmes' own human-readable context instead of re-slicing
    the Doc for text: `sentences_within_document` is the raw text of
    the matching sentence(s), and `search_phrase_text` is the phrase
    that was matched.
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

    word_matches: list[HolmesWordMatch]
    raw_match: dict[str, Any] | None = None

    def iter_content_words(self) -> Iterable[HolmesWordMatch]:
        """
        Yield word-matches that are not generic placeholders like
        'somebody'/'something'.
        """
        for wm in self.word_matches:
            if wm.document_word.lower() in {"somebody", "something"}:
                continue
            yield wm