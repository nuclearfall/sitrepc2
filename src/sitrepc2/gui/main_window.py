from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QStackedWidget,
    QToolBar,
)
from PySide6.QtGui import QAction

from sitrepc2.gui.ingest.ingest_workspace import IngestWorkspace
from sitrepc2.gui.review.review_workspace import DomReviewWorkspace


# ============================================================================
# Main Window
# ============================================================================
class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("sitrepc2")
        self.resize(1400, 900)

        self._build_ui()

    def _build_ui(self):
        self.workspace_stack = QStackedWidget()
        self.setCentralWidget(self.workspace_stack)

        self.ingest_workspace = IngestWorkspace(self)
        self.review_workspace = DomReviewWorkspace(parent=self)

        self.workspace_stack.addWidget(self.ingest_workspace)
        self.workspace_stack.addWidget(self.review_workspace)

        self._build_workspace_toolbar()
        self.show_ingest()

    def _build_workspace_toolbar(self):
        toolbar = QToolBar("Workspaces", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self.action_ingest = QAction("Ingest", self, checkable=True)
        self.action_review = QAction("Review", self, checkable=True)

        from PySide6.QtGui import QActionGroup
        group = QActionGroup(self)
        group.setExclusive(True)
        group.addAction(self.action_ingest)
        group.addAction(self.action_review)

        toolbar.addAction(self.action_ingest)
        toolbar.addAction(self.action_review)

        self.action_ingest.triggered.connect(self.show_ingest)
        self.action_review.triggered.connect(self.show_review)

    def show_ingest(self):
        self.workspace_stack.setCurrentWidget(self.ingest_workspace)
        self.action_ingest.setChecked(True)

    def show_review(self):
        self.workspace_stack.setCurrentWidget(self.review_workspace)
        self.action_review.setChecked(True)

