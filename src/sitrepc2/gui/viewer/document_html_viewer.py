from __future__ import annotations

from typing import Dict, Optional, List

from PySide6.QtCore import Signal, QUrl, QObject, Slot
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel

from spacy.tokens import Doc, Token, Span


# ---------------------------------------------------------------------
# JS bridge
# ---------------------------------------------------------------------

class _JsBridge(QObject):
    tokenClicked = Signal(int, object)
    tokensSelected = Signal(list)  # list[int]

    @Slot(int, str)
    def onTokenClicked(self, token_i: int, span_id: str) -> None:
        self.tokenClicked.emit(token_i, span_id or None)

    @Slot(list)
    def onTokensSelected(self, token_indices: list[int]) -> None:
        self.tokensSelected.emit(token_indices)


# ---------------------------------------------------------------------
# Viewer
# ---------------------------------------------------------------------

class DocumentHtmlViewer(QWebEngineView):
    """
    HTML-based interactive viewer for spaCy Docs.

    Guarantees:
    - Token-precise DOM nodes
    - Unified entity span highlighting (incl. whitespace)
    - Unified tooltip per entity (hover anywhere in entity)
    - Multi-token selection ONLY for non-entity tokens
    """

    tokenSelected = Signal(object, object)      # Token, Optional[Span]
    tokensSelected = Signal(list)               # list[Token]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._doc: Optional[Doc] = None
        self._span_map: Dict[str, Span] = {}

        self._bridge = _JsBridge()
        self._bridge.tokenClicked.connect(self._on_token_clicked)
        self._bridge.tokensSelected.connect(self._on_tokens_selected)

        channel = QWebChannel(self.page())
        channel.registerObject("bridge", self._bridge)
        self.page().setWebChannel(channel)

    # ------------------------------------------------------------------

    def set_doc(self, doc: Doc, *, ruler_colors: Dict[str, str]) -> None:
        self._doc = doc
        self._span_map.clear()
        self.setHtml(self._build_html(doc, ruler_colors), QUrl("qrc:///"))

    # ------------------------------------------------------------------

    def _on_token_clicked(self, token_i: int, span_id: Optional[str]) -> None:
        if not self._doc:
            return
        token = self._doc[token_i]
        span = self._span_map.get(span_id) if span_id else None
        self.tokenSelected.emit(token, span)

    def _on_tokens_selected(self, token_indices: List[int]) -> None:
        if not self._doc or not token_indices:
            return
        tokens = [self._doc[i] for i in token_indices]
        self.tokensSelected.emit(tokens)

    # ------------------------------------------------------------------

    def _build_html(self, doc: Doc, ruler_colors: Dict[str, str]) -> str:
        spans_by_token: Dict[int, str] = {}
        span_labels: Dict[int, str] = {}
        span_first: Dict[int, bool] = {}
        span_last: Dict[int, bool] = {}

        for idx, span in enumerate(doc.ents):
            span_id = f"span_{idx}"
            self._span_map[span_id] = span

            for i, tok in enumerate(span):
                spans_by_token[tok.i] = span_id
                span_labels[tok.i] = span.label_
                if i == 0:
                    span_first[tok.i] = True
                if i == len(span) - 1:
                    span_last[tok.i] = True

        css = self._build_css(ruler_colors)
        body: list[str] = []

        # Emit tokens: entity tokens absorb their own whitespace for unified highlighting
        for tok in doc:
            span_id = spans_by_token.get(tok.i, "")
            label = span_labels.get(tok.i, "")

            attrs = [
                'class="token"',
                f'data-token-i="{tok.i}"',
                f'data-span-id="{span_id}"',
            ]

            if label:
                attrs.append(f'data-entity-label="{label}"')
                if span_first.get(tok.i):
                    attrs.append('data-span-first="1"')
                if span_last.get(tok.i):
                    attrs.append('data-span-last="1"')

                # absorb whitespace inside entity span so gaps highlight too
                text = tok.text + tok.whitespace_
                trailing = ""
            else:
                text = tok.text
                trailing = tok.whitespace_

            body.append(f"<span {' '.join(attrs)}>{text}</span>{trailing}")

        # NOTE: We must escape braces in f-string JS by doubling them.
        return (
            "<!DOCTYPE html>"
            "<html><head>"
            '<meta charset="utf-8">'
            f"<style>{css}</style>"
            '<script src="qrc:///qtwebchannel/qwebchannel.js"></script>'
            "<script>"
            "new QWebChannel(qt.webChannelTransport, function(channel) {"
            "  window.bridge = channel.objects.bridge;"
            "});"

            # ------------------------------------------------------------
            # Unified entity hover tooltip (hover anywhere in span)
            # ------------------------------------------------------------
            "let hoveredSpanId = null;"
            "function setSpanHover(spanId, on) {"
            "  if (!spanId) return;"
            "  const first = document.querySelector("
            "    '.token[data-span-id=\"' + spanId + '\"][data-span-first]'"
            "  );"
            "  if (!first) return;"
            "  if (on) first.classList.add('span-hover');"
            "  else first.classList.remove('span-hover');"
            "}"
            "document.addEventListener('mouseover', function(e) {"
            "  const el = e.target.closest('.token[data-span-id]');"
            "  if (!el) return;"
            "  const spanId = el.dataset.spanId || '';"
            "  if (!spanId) return;"
            "  if (hoveredSpanId && hoveredSpanId !== spanId) {"
            "    setSpanHover(hoveredSpanId, false);"
            "  }"
            "  hoveredSpanId = spanId;"
            "  setSpanHover(spanId, true);"
            "});"
            "document.addEventListener('mouseout', function(e) {"
            "  const el = e.target.closest('.token[data-span-id]');"
            "  if (!el) return;"
            "  const spanId = el.dataset.spanId || '';"
            "  if (!spanId) return;"
            "  // Only clear if we actually left the span region"
            "  // (mouseout fires for internal moves too; this is a best-effort)"
            "  setSpanHover(spanId, false);"
            "  if (hoveredSpanId === spanId) hoveredSpanId = null;"
            "});"

            # ------------------------------------------------------------
            # Token selection logic (ONLY non-entity tokens)
            # - Click+drag selects contiguous token index range
            # - Excludes tokens with data-entity-label
            # - Suppresses click passthrough after a drag selection
            # ------------------------------------------------------------
            "let selStart = null;"
            "let selected = new Set();"
            "let isSelecting = false;"
            "let didDragSelect = false;"

            "function isSelectableToken(el) {"
            "  if (!el) return false;"
            "  // Non-entity only"
            "  return !el.hasAttribute('data-entity-label');"
            "}"

            "function clearSelection() {"
            "  document.querySelectorAll('.token.selected').forEach(el => {"
            "    el.classList.remove('selected');"
            "  });"
            "  selected.clear();"
            "}"

            "function applyRange(a, b) {"
            "  clearSelection();"
            "  const lo = Math.min(a, b);"
            "  const hi = Math.max(a, b);"
            "  for (let i = lo; i <= hi; i++) {"
            "    const t = document.querySelector('.token[data-token-i=\"' + i + '\"]');"
            "    if (!t) continue;"
            "    if (!isSelectableToken(t)) continue;"
            "    t.classList.add('selected');"
            "    selected.add(i);"
            "  }"
            "}"

            "document.addEventListener('mousedown', function(e) {"
            "  const el = e.target.closest('.token');"
            "  if (!el) return;"
            "  if (!isSelectableToken(el)) {"
            "    // do not begin selection on entity tokens"
            "    selStart = null;"
            "    isSelecting = false;"
            "    didDragSelect = false;"
            "    return;"
            "  }"
            "  selStart = parseInt(el.dataset.tokenI);"
            "  isSelecting = true;"
            "  didDragSelect = false;"
            "  applyRange(selStart, selStart);"
            "});"

            "document.addEventListener('mousemove', function(e) {"
            "  if (!isSelecting || selStart === null) return;"
            "  const el = e.target.closest('.token');"
            "  if (!el) return;"
            "  const cur = parseInt(el.dataset.tokenI);"
            "  if (cur !== selStart) didDragSelect = true;"
            "  applyRange(selStart, cur);"
            "});"

            "document.addEventListener('mouseup', function(e) {"
            "  if (!isSelecting) return;"
            "  if (selected.size > 0) {"
            "    bridge.onTokensSelected(Array.from(selected));"
            "  }"
            "  isSelecting = false;"
            "  selStart = null;"
            "  // allow click suppression in the following click handler"
            "});"

            # ------------------------------------------------------------
            # Click passthrough (token click / entity click)
            # Suppress if drag selection occurred.
            # ------------------------------------------------------------
            "document.addEventListener('click', function(e) {"
            "  if (didDragSelect) {"
            "    didDragSelect = false;"
            "    return;"
            "  }"
            "  const el = e.target.closest('.token');"
            "  if (!el) return;"
            "  bridge.onTokenClicked("
            "    parseInt(el.dataset.tokenI),"
            "    el.dataset.spanId || ''"
            "  );"
            "});"

            "</script></head><body>"
            + "".join(body) +
            "</body></html>"
        )

    # ------------------------------------------------------------------

    @staticmethod
    def _build_css(ruler_colors: Dict[str, str]) -> str:
        rules = [
            "body { white-space: pre-wrap; }",
            ".token { position: relative; cursor: pointer; }",

            # Selection styling (non-entity only)
            ".token.selected { outline: 2px solid #444; }",

            # --- Unified entity highlight ---
            (
                ".token[data-entity-label] {"
                "  padding: 0.12em 0.18em;"
                "  box-decoration-break: clone;"
                "  -webkit-box-decoration-break: clone;"
                "}"
            ),

            # --- Collapse seams (entity tokens only) ---
            (
                ".token[data-entity-label]:not([data-span-first]) {"
                "  margin-left: -0.18em;"
                "}"
            ),

            # --- Rounded edges ---
            (
                ".token[data-span-first] {"
                "  border-top-left-radius: 0.45em;"
                "  border-bottom-left-radius: 0.45em;"
                "}"
            ),
            (
                ".token[data-span-last] {"
                "  border-top-right-radius: 0.45em;"
                "  border-bottom-right-radius: 0.45em;"
                "}"
            ),

            # --- Unified tooltip (JS applies .span-hover to first token) ---
            (
                ".token[data-span-first].span-hover::after {"
                "  content: attr(data-entity-label);"
                "  position: absolute;"
                "  top: -1.6em;"
                "  left: 0;"
                "  background: rgba(40,40,40,0.95);"
                "  color: #fff;"
                "  font-size: 0.75em;"
                "  padding: 2px 6px;"
                "  border-radius: 4px;"
                "  white-space: nowrap;"
                "  pointer-events: none;"
                "  z-index: 1000;"
                "}"
            ),
        ]

        for label, color in ruler_colors.items():
            rules.append(
                f'.token[data-entity-label="{label}"] {{ '
                f'background-color: {color}; '
                f'}}'
            )

        return "\n".join(rules)
