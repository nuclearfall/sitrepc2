# src/sitrepc2/gui/controller/document_controller.py
from __future__ import annotations

from typing import Optional

import spacy
from spacy.language import Language
from spacy.tokens import Doc

from sitrepc2.lss.ruler import add_entity_rulers_from_db


class DocumentController:
    """
    Owns the spaCy pipeline and document lifecycle.

    Responsibilities:
    - Build and own spaCy Language pipeline
    - Install DB-backed EntityRuler patterns
    - Load raw text
    - Rebuild Doc deterministically
    - Reload rulers when gazetteer aliases change

    Notes:
    - Docs are treated as ephemeral artifacts
    - Pipeline is authoritative
    """

    def __init__(
        self,
        *,
        spacy_model: str,
        enable_coreferee: bool,
    ) -> None:
        self.spacy_model = spacy_model
        self.enable_coreferee = enable_coreferee

        self.nlp: Language = self._build_pipeline()
        self.doc: Optional[Doc] = None

        # Authoritative input text
        self._raw_text: Optional[str] = None

    # ------------------------------------------------------------------
    # Pipeline construction
    # ------------------------------------------------------------------

    def _build_pipeline(self) -> Language:
        nlp = spacy.load(self.spacy_model)

        if self.enable_coreferee:
            import coreferee  # noqa: F401
            if "coreferee" not in nlp.pipe_names:
                nlp.add_pipe("coreferee")

        # Initial DB-backed ruler install
        add_entity_rulers_from_db(nlp)

        return nlp

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_text(self, text: str) -> Doc:
        """
        Load new raw text and build a fresh Doc.
        """
        self._raw_text = text
        self.doc = self.nlp(text)
        return self.doc

    def rebuild_doc(self) -> Optional[Doc]:
        """
        Rebuild the Doc from the last loaded raw text.

        Safe to call repeatedly.
        """
        if not self._raw_text:
            self.doc = None
            return None

        self.doc = self.nlp(self._raw_text)
        return self.doc

    def reload_entity_rulers(self) -> None:
        """
        Reload EntityRuler patterns from gazetteer.db.

        This:
        - Removes the existing custom_entity_ruler
        - Reinstalls patterns from the aliases table
        - Does NOT rebuild the Doc automatically
        """
        add_entity_rulers_from_db(self.nlp)

    # ------------------------------------------------------------------
    # Convenience helper (optional but recommended)
    # ------------------------------------------------------------------

    def reload_rulers_and_rebuild(self) -> Optional[Doc]:
        """
        Convenience method for UI callers.

        Typical use:
            controller.reload_rulers_and_rebuild()
        """
        self.reload_entity_rulers()
        return self.rebuild_doc()
