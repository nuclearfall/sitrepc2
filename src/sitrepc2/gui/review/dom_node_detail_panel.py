from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QTextEdit,
    QFormLayout,
    QCheckBox,
)

from sitrepc2.dom.nodes import DomNode


class DomNodeDetailPanel(QWidget):
    """
    Generic, read-only detail panel for any DomNode.

    Intentionally defensive:
    - does not assume node_type / node_id
    - reflects actual attributes present on the node
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.current_node: DomNode | None = None

        layout = QVBoxLayout(self)

        self.header = QLabel("DOM Node Details")
        self.header.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.header)

        form = QFormLayout()
        layout.addLayout(form)

        # Node "type" = class name
        self.node_class_label = QLabel("-")
        form.addRow("Node class:", self.node_class_label)

        # Selected state
        self.selected_checkbox = QCheckBox()
        self.selected_checkbox.setEnabled(False)
        form.addRow("Selected:", self.selected_checkbox)

        # Summary / text
        self.content_text = QTextEdit()
        self.content_text.setReadOnly(True)
        layout.addWidget(self.content_text)

        self.clear()

    # ------------------------------------------------------------

    def set_node(self, node: DomNode):
        self.current_node = node

        # Class name as type
        self.node_class_label.setText(node.__class__.__name__)

        # Selected flag (if present)
        self.selected_checkbox.setChecked(bool(getattr(node, "selected", False)))

        # Prefer summary, fall back to text, else repr
        if hasattr(node, "summary") and node.summary:
            content = node.summary
        elif hasattr(node, "text") and node.text:
            content = node.text
        else:
            content = repr(node)

        self.content_text.setPlainText(content)

    def clear(self):
        self.current_node = None
        self.node_class_label.setText("-")
        self.selected_checkbox.setChecked(False)
        self.content_text.clear()
