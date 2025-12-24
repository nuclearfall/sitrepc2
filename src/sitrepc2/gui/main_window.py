# src/sitrepc2/gui/main_window.py

from __future__ import annotations

from typing import Dict

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QStackedWidget,
)

from sitrepc2.gui.ingest.workspace import IngestWorkspace
from sitrepc2.gui.dom.workspace import DomReviewWorkspace
from sitrepc2.ingest.extract_lss import extract_posts_to_lss

from sitrepc2.gui.ingest.loaders import (
    load_ingest_posts,
    load_sources,
)



class MainWindow(QMainWindow):
    """
    Application shell.

    Responsibilities:
    - host workspaces
    - switch between them
    - manage workspace lifetimes
    """

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("SitRepC2")

        # --------------------------------------------------
        # Workspace container
        # --------------------------------------------------

        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        # --------------------------------------------------
        # Workspace registry
        # --------------------------------------------------

        self._workspaces: Dict[str, QWidget] = {}

        # --------------------------------------------------
        # Initial workspace: Ingest
        # --------------------------------------------------

        self._init_ingest_workspace()

    # ======================================================
    # Workspace initialization
    # ======================================================

    def _init_ingest_workspace(self) -> None:
        controller = IngestController(
            load_sources_fn=load_sources,
            load_posts_fn=load_ingest_posts,
            extract_fn=extract_posts_to_lss,
            on_open_dom=self.open_dom_review,
        )
     
        ingest_ws = IngestWorkspace(controller, parent=self)

        self._register_workspace("ingest", ingest_ws)
        self._show_workspace("ingest")

    # ======================================================
    # Workspace registration
    # ======================================================

    def _register_workspace(self, key: str, widget: QWidget) -> None:
        self._workspaces[key] = widget
        self._stack.addWidget(widget)

    def _show_workspace(self, key: str) -> None:
        widget = self._workspaces[key]
        self._stack.setCurrentWidget(widget)

    # ======================================================
    # Navigation entry points (called by controllers)
    # ======================================================

    def open_dom_review(self, ingest_post_id: int) -> None:
        """
        Open (or re-open) DOM review for a given ingest post.
        """

        key = f"dom:{ingest_post_id}"

        if key not in self._workspaces:
            dom_ws = DomReviewWorkspace(
                ingest_post_id=ingest_post_id,
                on_done=self.return_to_ingest,
            )
            self._register_workspace(key, dom_ws)

        self._show_workspace(key)

    def return_to_ingest(self) -> None:
        """
        Return to ingest workspace.
        """
        self._show_workspace("ingest")
