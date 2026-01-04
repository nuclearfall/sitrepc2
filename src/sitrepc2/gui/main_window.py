from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QStackedWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QToolBar,
    QAction
)

from sitrepc2.gui.ingest.ingest_workspace import IngestWorkspace
from sitrepc2.gui.review.review_workspace import ReviewWorkspace


# ============================================================================
# Main Window
# ============================================================================

class MainWindow(QMainWindow):
    """
    Main application window for sitrepc2 GUI.

    Responsibilities:
    - Own workspace lifecycle
    - Host workspace stack
    - Coordinate explicit navigation
    """

    # ------------------------------------------------------------------

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("sitrepc2")
        self.resize(1400, 900)

        self._build_ui()
        self._wire_signals()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.workspace_stack = QStackedWidget()
        self.setCentralWidget(self.workspace_stack)

        self.ingest_workspace = IngestWorkspace(self)
        self.review_workspace = ReviewWorkspace(self)

        self.workspace_stack.addWidget(self.ingest_workspace)
        self.workspace_stack.addWidget(self.review_workspace)

        self._build_workspace_toolbar()

        self.workspace_stack.setCurrentWidget(self.ingest_workspace)


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

        # Default
        self.action_ingest.setChecked(True)

        self.action_ingest.triggered.connect(self.show_ingest)
        self.action_review.triggered.connect(self.show_review)

    # ------------------------------------------------------------------
    # Wiring
    # ------------------------------------------------------------------

    def _wire_signals(self) -> None:
        self.btn_ingest.clicked.connect(self.show_ingest)
        self.btn_review.clicked.connect(self.show_review)


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
