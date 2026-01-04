from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QStackedWidget,
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

        # 🔗 navigation wiring
        self.ingest_workspace.review_requested.connect(self.show_review)

        self.workspace_stack.setCurrentWidget(self.ingest_workspace)


    # ------------------------------------------------------------------
    # Wiring
    # ------------------------------------------------------------------

    def _wire_signals(self) -> None:
        self.ingest_workspace.extraction_completed.connect(
            self.show_review
        )

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def show_ingest(self) -> None:
        self.workspace_stack.setCurrentWidget(self.ingest_workspace)

    def show_review(self) -> None:
        self.workspace_stack.setCurrentWidget(self.review_workspace)
