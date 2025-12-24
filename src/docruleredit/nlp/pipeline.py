from __future__ import annotations

from typing import Iterable, Optional

import spacy

try:
    import coreferee  # noqa: F401
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "coreferee is required but not installed. "
        "Install it with: pip install coreferee"
    ) from exc


class NLPPipeline:
    """
    Responsible for constructing and managing the spaCy NLP pipeline.

    Constraints:
    - spaCy + coreferee only
    - No Holmes integration
    - EntityRuler components are attached dynamically by the controller

    This class does NOT own document state.
    """

    def __init__(self, model: str = "en_core_web_lg") -> None:
        self.model_name = model
        self.nlp = self._build_pipeline()

    # ------------------------------------------------------------------
    # Pipeline construction
    # ------------------------------------------------------------------

    def _build_pipeline(self) -> spacy.Language:
        """
        Build the base spaCy pipeline and enable coreference resolution.
        """
        nlp = spacy.load(self.model_name)

        if "coreferee" not in nlp.pipe_names:
            nlp.add_pipe("coreferee")

        return nlp

    # ------------------------------------------------------------------
    # EntityRuler management
    # ------------------------------------------------------------------

    def ensure_entity_ruler(self, name: str = "user_entity_ruler") -> None:
        """
        Ensure that an EntityRuler with the given name exists in the pipeline.

        The ruler is inserted before the 'ner' component when possible.
        """
        if name in self.nlp.pipe_names:
            return

        insert_before = "ner" if "ner" in self.nlp.pipe_names else None
        self.nlp.add_pipe(
            "entity_ruler",
            name=name,
            before=insert_before,
        )

    def remove_entity_ruler(self, name: str) -> None:
        """
        Remove an EntityRuler from the pipeline if it exists.
        """
        if name in self.nlp.pipe_names:
            self.nlp.remove_pipe(name)

    def get_entity_ruler(self, name: str):
        """
        Retrieve an EntityRuler component by name.

        Raises KeyError if the ruler does not exist.
        """
        return self.nlp.get_pipe(name)

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------

    def process_text(self, text: str) -> spacy.tokens.Doc:
        """
        Process raw text into a spaCy Doc using the current pipeline.
        """
        return self.nlp(text)
