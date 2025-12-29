from __future__ import annotations

from PySide6.QtWidgets import (
    QMainWindow,
    QTabWidget,
    QWidget,
    QVBoxLayout,
)

from dbeditc2.location_ws import LocationWorkspace
from dbeditc2.lexicon_ws import LexiconWorkspace


class MainWindow(QMainWindow):
    """
    Main application window.

    Responsibilities:
    - Own application-level layout
    - Host workspaces
    - Display global status messages

    Contains NO domain logic.
    """

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("dbeditc2")
        self.resize(600, 800)

        # --------------------------------------------------
        # Workspace tabs
        # --------------------------------------------------

        self._tabs = QTabWidget(self)
        self.setCentralWidget(self._tabs)

        # Location workspace
        self._location_ws = LocationWorkspace(self)
        self._location_ws.statusMessage.connect(self._show_status)

        self._tabs.addTab(
            self._location_ws,
            "Locations",
        )

        # Lexicon workspace
        self._lexicon_ws = LexiconWorkspace(self)
        self._lexicon_ws.statusMessage.connect(self._show_status)

        self._tabs.addTab(
            self._lexicon_ws,
            "Lexicon",
        )

        # --------------------------------------------------
        # Status bar
        # --------------------------------------------------

        self.statusBar().showMessage("Ready")

    # --------------------------------------------------
    # Shared UI services
    # --------------------------------------------------

    def _show_status(self, text: str) -> None:
        self.statusBar().showMessage(text)
