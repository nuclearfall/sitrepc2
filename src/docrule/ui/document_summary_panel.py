from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QTextEdit
from PySide6.QtGui import QTextDocument

from spacy.tokens import Doc


class DocumentSummaryPanel(QTextEdit):
    """
    Read-only panel that displays a high-level summary of
    spaCy and coreferee processing for the active document.

    This panel is rebuilt only when a new document is loaded.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setAcceptRichText(False)
        self.setPlaceholderText(
            "Document summary will appear here after processing."
        )

    def set_doc(self, doc: Optional[Doc]) -> None:
        """
        Render a summary for the given spaCy Doc.
        """
        if doc is None:
            self.clear()
            return

        lines: list[str] = []

        # Basic document stats
        lines.append(f"Tokens: {len(doc)}")
        lines.append(f"Sentences: {len(list(doc.sents))}")
        lines.append(f"Named Entities: {len(doc.ents)}")

        # Pipeline info
        lines.append("")
        lines.append("Pipeline components:")
        for name in doc.vocab.lang:
            pass  # placeholder for language; keep summary minimal

        # Coreference info (presence only)
        lines.append("")
        if hasattr(doc._, "coref_chains"):
            chains = doc._.coref_chains
            lines.append(f"Coreference chains: {len(chains)}")
        else:
            lines.append("Coreference chains: unavailable")

        self.setPlainText("\n".join(lines))
