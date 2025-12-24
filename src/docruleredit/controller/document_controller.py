from __future__ import annotations

from typing import Iterable, List, Optional

from spacy.tokens import Doc

from ..nlp.pipeline import NLPPipeline


class DocumentController:
    """
    Central coordinator for document state.

    Responsibilities:
    - Own the active spaCy Doc
    - Own the NLP pipeline
    - Manage user EntityRulers (attachment only; definitions live elsewhere)
    - Normalize all document ingress paths into:
        raw_text -> Doc -> UI refresh

    GUI components should interact with the document ONLY through this class.
    """

    def __init__(self) -> None:
        self.pipeline = NLPPipeline()
        self.doc: Optional[Doc] = None

        # Name reserved for the user-controlled EntityRuler component
        self._user_ruler_name = "user_entity_ruler"

        # Ensure the ruler exists up front
        self.pipeline.ensure_entity_ruler(self._user_ruler_name)

    # ------------------------------------------------------------------
    # Document lifecycle
    # ------------------------------------------------------------------

    def load_text(self, text: str) -> Doc:
        """
        Replace the current document with a new one created from raw text.

        This always produces a new spaCy Doc and discards any existing one.
        """
        self.doc = self.pipeline.process_text(text)
        return self.doc

    def clear_document(self) -> None:
        """
        Clear the current document.
        """
        self.doc = None

    # ------------------------------------------------------------------
    # EntityRuler access
    # ------------------------------------------------------------------

    def get_user_entity_ruler(self):
        """
        Return the user-controlled EntityRuler component.
        """
        return self.pipeline.get_entity_ruler(self._user_ruler_name)

    def reset_user_entity_ruler(self) -> None:
        """
        Remove and recreate the user EntityRuler.

        Useful when reloading rulers from disk.
        """
        self.pipeline.remove_entity_ruler(self._user_ruler_name)
        self.pipeline.ensure_entity_ruler(self._user_ruler_name)

    # ------------------------------------------------------------------
    # Reprocessing
    # ------------------------------------------------------------------

    def rebuild_doc(self) -> Optional[Doc]:
        """
        Re-run the NLP pipeline on the current document text.

        Used when entity rulers or pipeline configuration changes.
        """
        if self.doc is None:
            return None

        text = self.doc.text
        self.doc = self.pipeline.process_text(text)
        return self.doc
