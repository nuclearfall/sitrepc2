import sqlite3

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QTextEdit,
    QPushButton,
    QMessageBox,
)

from sitrepc2.dom.nodes import DomNode, LocationNode, LocationCandidateNode
from sitrepc2.dom.dom_persist_tree import persist_dom_tree


class LocationDetailPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.current_node: LocationNode | None = None
        self.root_node: DomNode | None = None
        self.snapshot_id: int | None = None
        self.db_path: str | None = None

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.summary_label = QLabel("Location Summary")
        self.layout.addWidget(self.summary_label)

        self.summary_text = QTextEdit()
        self.layout.addWidget(self.summary_text)

        self.candidates_label = QLabel("Candidates")
        self.layout.addWidget(self.candidates_label)

        self.candidates_text = QTextEdit()
        self.layout.addWidget(self.candidates_text)

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.on_save)
        self.layout.addWidget(self.save_button)

    def set_node(self, node: DomNode, root: DomNode, snapshot_id: int, db_path: str):
        if not isinstance(node, LocationNode):
            self.clear()
            return

        self.current_node = node
        self.root_node = root
        self.snapshot_id = snapshot_id
        self.db_path = db_path

        self.summary_text.setText(node.summary)

        candidates = [
            f"{c.name} ({'✓' if c.selected else '✗'})"
            for c in node.children
            if isinstance(c, LocationCandidateNode)
        ]
        self.candidates_text.setText("\n".join(candidates))

    def clear(self):
        self.current_node = None
        self.root_node = None
        self.snapshot_id = None
        self.db_path = None
        self.summary_text.clear()
        self.candidates_text.clear()

    def on_save(self):
        if not self.snapshot_id or not self.root_node or not self.db_path:
            QMessageBox.warning(self, "Error", "Missing data to persist DOM tree.")
            return

        confirm = QMessageBox.question(
            self,
            "Confirm Save",
            "This will overwrite existing review data. Continue?",
        )

        if confirm == QMessageBox.StandardButton.Yes:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    persist_dom_tree(
                        conn=conn,
                        dom_snapshot_id=self.snapshot_id,
                        root=self.root_node,
                    )
                QMessageBox.information(self, "Success", "Changes saved successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save: {e}")
