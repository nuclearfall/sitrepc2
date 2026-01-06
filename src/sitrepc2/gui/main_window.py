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
    """
    Main application window for sitrepc2 GUI.

    Responsibilities:
    - Own workspace lifecycle
    - Host workspace stack
    - Provide explicit workspace navigation
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("sitrepc2")
        self.resize(1400, 900)

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Central workspace stack
        self.workspace_stack = QStackedWidget()
        self.setCentralWidget(self.workspace_stack)

        # Workspaces
        self.ingest_workspace = IngestWorkspace(self)
        self.review_workspace = DomReviewWorkspace(self)

        self.workspace_stack.addWidget(self.ingest_workspace)
        self.workspace_stack.addWidget(self.review_workspace)

        # Workspace selector toolbar
        self._build_workspace_toolbar()

        # Default workspace
        self.show_ingest()

    def _build_workspace_toolbar(self) -> None:
        toolbar = QToolBar("Workspaces", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self.action_ingest = QAction("Ingest", self)
        self.action_ingest.setCheckable(True)

        self.action_review = QAction("Review", self)
        self.action_review.setCheckable(True)

        toolbar.addAction(self.action_ingest)
        toolbar.addAction(self.action_review)

        self.action_ingest.triggered.connect(self.show_ingest)
        self.action_review.triggered.connect(self.show_review)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def show_ingest(self) -> None:
        self.workspace_stack.setCurrentWidget(self.ingest_workspace)
        self.action_ingest.setChecked(True)
        self.action_review.setChecked(False)

    def show_review(self) -> None:
        self.workspace_stack.setCurrentWidget(self.review_workspace)
        self.action_ingest.setChecked(False)
        self.action_review.setChecked(True)
