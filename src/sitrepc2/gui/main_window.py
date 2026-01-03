from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QStackedWidget,
    QApplication,
)

from sitrepc2.gui.ingest.ingest_workspace import IngestWorkspace


# ============================================================================
# Main Window
# ============================================================================

class MainWindow(QMainWindow):
    """
    Main application window for sitrepc2 GUI.

    Responsibilities:
    - Own workspace lifecycle
    - Host workspace stack
    - Coordinate navigation (later)

    Currently hosts:
    - IngestWorkspace only
    """

    # ------------------------------------------------------------------

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("sitrepc2")
        self.resize(1400, 900)

        self._build_ui()

    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.workspace_stack = QStackedWidget()
        self.setCentralWidget(self.workspace_stack)

        # --------------------------------------------------------------
        # Workspaces
        # --------------------------------------------------------------

        self.ingest_workspace = IngestWorkspace(self)
        self.workspace_stack.addWidget(self.ingest_workspace)

        # Default workspace
        self.workspace_stack.setCurrentWidget(self.ingest_workspace)

    # ------------------------------------------------------------------
    # Future hooks (navigation, menus, etc.)
    # ------------------------------------------------------------------

    def show_ingest(self) -> None:
        self.workspace_stack.setCurrentWidget(self.ingest_workspace)
