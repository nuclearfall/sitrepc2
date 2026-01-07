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
    Intended for review/debug visibility.
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

        self.node_type_label = QLabel("-")
        form.addRow("Node type:", self.node_type_label)

        self.node_id_label = QLabel("-")
        form.addRow("Node id:", self.node_id_label)

        self.selected_checkbox = QCheckBox()
        self.selected_checkbox.setEnabled(False)
        form.addRow("Selected:", self.selected_checkbox)

        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        layout.addWidget(self.summary_text)

        self.clear()

    # ------------------------------------------------------------

    def set_node(self, node: DomNode):
        self.current_node = node

        self.node_type_label.setText(node.node_type)
        self.node_id_label.setText(str(node.node_id))
        self.selected_checkbox.setChecked(bool(node.selected))

        summary = getattr(node, "summary", None)
        self.summary_text.setPlainText(summary or "")

    def clear(self):
        self.current_node = None
        self.node_type_label.setText("-")
        self.node_id_label.setText("-")
        self.selected_checkbox.setChecked(False)
        self.summary_text.clear()
