from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import (
    QTextCursor,
    QTextCharFormat,
    QColor,
    QMouseEvent,
)
from PySide6.QtWidgets import QTextEdit

from spacy.tokens import Doc, Token, Span


class DocumentViewer(QTextEdit):
    """
    Read-only interactive viewer for a spaCy Doc.

    Responsibilities:
    - Render document text
    - Highlight entity spans
    - Provide hover + click interaction
    - Intercept paste / drag-drop as document replacement

    Emits:
    - tokenSelected(token, span_or_none)
    """

    tokenSelected = Signal(object, object)  # Token, Optional[Span]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.setReadOnly(True)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)

        self._doc: Optional[Doc] = None

        # Index: character offset -> token
        self._offset_to_token: Dict[int, Token] = {}

        # List of spans (spaCy entities + user rulers)
        self._spans: List[Span] = []

        # Hover state
        self._last_hover_cursor: Optional[QTextCursor] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_doc(
        self,
        doc: Doc,
        *,
        ruler_colors: Dict[str, str],
    ) -> None:
        """
        Render a spaCy Doc into the viewer.

        Args:
            ruler_colors:
                Mapping of entity label -> hex color
                (user EntityRuler only)
        """
        self.clear()

        self._doc = doc
        self._offset_to_token.clear()
        self._spans.clear()

        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.Start)

        # Build text and token index
        for token in doc:
            start_pos = cursor.position()
            cursor.insertText(token.text_with_ws)
            self._offset_to_token[start_pos] = token

        self._collect_spans()
        self._apply_highlighting(ruler_colors)

        cursor.movePosition(QTextCursor.Start)
        self.setTextCursor(cursor)

    # ------------------------------------------------------------------
    # Span collection & highlighting
    # ------------------------------------------------------------------

    def _collect_spans(self) -> None:
        """
        Collect all spans relevant for interaction.
        """
        if not self._doc:
            return

        # spaCy named entities
        self._spans.extend(self._doc.ents)

        # User EntityRuler spans also appear in doc.ents
        # We rely on label/color mapping to differentiate

    def _apply_highlighting(self, ruler_colors: Dict[str, str]) -> None:
        """
        Apply highlighting for entity spans.

        User rulers: colored background
        Built-in spaCy entities: subtle underline
        """
        cursor = self.textCursor()

        for span in self._spans:
            start = span.start_char
            end = span.end_char

            fmt = QTextCharFormat()

            label = span.label_
            if label in ruler_colors:
                fmt.setBackground(QColor(ruler_colors[label]))
            else:
                fmt.setUnderlineStyle(QTextCharFormat.DotLine)
                fmt.setUnderlineColor(QColor("#888888"))

            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)
            cursor.mergeCharFormat(fmt)

    # ------------------------------------------------------------------
    # Hover & click handling
    # ------------------------------------------------------------------

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        cursor = self.cursorForPosition(event.position().toPoint())
        self._update_hover(cursor)
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        cursor = self.cursorForPosition(event.position().toPoint())
        token = self._token_at_cursor(cursor)
        span = self._span_for_token(token) if token else None

        if token:
            self.tokenSelected.emit(token, span)

        super().mousePressEvent(event)

    def _update_hover(self, cursor: QTextCursor) -> None:
        """
        Apply a dotted hover outline around the token/span.
        """
        if cursor == self._last_hover_cursor:
            return

        self._clear_hover()

        token = self._token_at_cursor(cursor)
        if not token:
            return

        span = self._span_for_token(token)
        start = span.start_char if span else token.idx
        end = span.end_char if span else token.idx + len(token)

        fmt = QTextCharFormat()
        fmt.setProperty(QTextCharFormat.OutlinePen, Qt.DotLine)

        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        cursor.mergeCharFormat(fmt)

        self._last_hover_cursor = cursor

    def _clear_hover(self) -> None:
        # Hover formatting is non-destructive; no-op placeholder
        pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _token_at_cursor(self, cursor: QTextCursor) -> Optional[Token]:
        if not self._doc:
            return None

        pos = cursor.position()
        return self._offset_to_token.get(pos)

    def _span_for_token(self, token: Token) -> Optional[Span]:
        for span in self._spans:
            if token.i >= span.start and token.i < span.end:
                return span
        return None

    # ------------------------------------------------------------------
    # Clipboard & drag-drop interception
    # ------------------------------------------------------------------

    def insertFromMimeData(self, source) -> None:
        """
        Intercept paste: treat as new document.
        """
        text = source.text()
        if text:
            self.parent().load_text_from_external(text)

    def dropEvent(self, event) -> None:
        """
        Intercept drag-drop: delegate to parent.
        """
        mime = event.mimeData()

        if mime.hasUrls():
            for url in mime.urls():
                self.parent().load_file_from_external(url.toLocalFile())
        elif mime.hasText():
            self.parent().load_text_from_external(mime.text())
