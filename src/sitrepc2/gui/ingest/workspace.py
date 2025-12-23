from __future__ import annotations

from typing import Optional
from datetime import date, timedelta


from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QTableView,
    QPushButton,
    QLabel,
    QLineEdit,
    QDateEdit,
    QSizePolicy,
)

from sitrepc2.gui.ingest.ingest_controller import IngestController
from sitrepc2.gui.ingest.sources_table_model import SourcesTableModel
from sitrepc2.gui.ingest.posts_table_model import IngestPostsTableModel
from sitrepc2.gui.ingest.typedefs import IngestState
from sitrepc2.gui.ingest.progress import LssProgress

class IngestWorkspace(QWidget):
    """
    Fully wired ingest workspace.

    GUI only — all logic lives in IngestController.
    """

    def __init__(
        self,
        controller: IngestController,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self.controller = controller

        # ----------------------------------------------------
        # Widgets
        # ----------------------------------------------------

        self.sources_view = QTableView()
        self.posts_view = QTableView()

        self.add_source_button = QPushButton("Add Source")
        self.fetch_button = QPushButton("Fetch")
        self.extract_button = QPushButton("Extract (LSS)")
        self.open_dom_button = QPushButton("Open DOM Review")
        self.open_dom_button.setEnabled(False)

        self.start_date = QDateEdit()
        self.end_date = QDateEdit()
        self.whitelist_input = QLineEdit()
        self.blacklist_input = QLineEdit()

        self.whitelist_input.setPlaceholderText("Whitelist keywords")
        self.blacklist_input.setPlaceholderText("Blacklist keywords")

        self.status_label = QLabel("")
        self.status_label.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Preferred
        )

        # ----------------------------------------------------
        # Default date range: yesterday → yesterday
        # ----------------------------------------------------

        yesterday = date.today() - timedelta(days=1)

        self.start_date.setDate(yesterday)
        self.end_date.setDate(yesterday)

        self.controller.set_date_range(yesterday, yesterday)
        self.controller.set_lss_progress_handler(self._on_lss_progress)


        # ----------------------------------------------------
        # Models
        # ----------------------------------------------------

        self.sources_model = SourcesTableModel(controller)
        self.posts_model = IngestPostsTableModel(controller)

        self.sources_view.setModel(self.sources_model)
        self.posts_view.setModel(self.posts_model)

        # ----------------------------------------------------
        # Layout
        # ----------------------------------------------------

        self._init_layout()

        # ----------------------------------------------------
        # Signals
        # ----------------------------------------------------

        self.add_source_button.clicked.connect(
            self.sources_model.add_empty_source 
        )

        self.fetch_button.clicked.connect(self._on_fetch_clicked)
        self.extract_button.clicked.connect(self._on_extract_clicked)
        self.open_dom_button.clicked.connect(self._open_dom_review)

        self.start_date.dateChanged.connect(self._on_filters_changed)
        self.end_date.dateChanged.connect(self._on_filters_changed)
        self.whitelist_input.textChanged.connect(self._on_filters_changed)
        self.blacklist_input.textChanged.connect(self._on_filters_changed)

        # Selection → button enablement
        self.posts_view.selectionModel().selectionChanged.connect(
            lambda *_: self._refresh_action_buttons()
        )

        # Controller → UI updates
        self.controller._on_state_changed = self._refresh_views

        # ----------------------------------------------------
        # Initial load
        # ----------------------------------------------------

        self.controller.load_sources()
        self.controller.load_posts()

        self._refresh_views()

    # ========================================================
    # Layout
    # ========================================================

    def _init_layout(self) -> None:
        root = QVBoxLayout(self)

        # ---- Controls bar ----
        controls = QHBoxLayout()
        controls.addWidget(QLabel("From:"))
        controls.addWidget(self.start_date)
        controls.addWidget(QLabel("To:"))
        controls.addWidget(self.end_date)
        controls.addWidget(self.whitelist_input)
        controls.addWidget(self.blacklist_input)
        controls.addWidget(self.fetch_button)
        controls.addWidget(self.extract_button)
        controls.addWidget(self.open_dom_button)
        controls.addWidget(self.status_label)

        root.addLayout(controls)

        # ---- Main panes ----
        panes = QHBoxLayout()

        # Sources pane
        sources_layout = QVBoxLayout()
        sources_layout.addWidget(QLabel("Sources"))
        sources_layout.addWidget(self.sources_view)

        sources_buttons = QHBoxLayout()
        sources_buttons.addWidget(self.add_source_button)
        sources_buttons.addStretch(1)

        sources_layout.addLayout(sources_buttons)

        sources_container = QWidget()
        sources_container.setLayout(sources_layout)
        sources_container.setMinimumWidth(300)

        panes.addWidget(sources_container, 1)

        # Posts pane
        posts_layout = QVBoxLayout()
        posts_layout.addWidget(QLabel("Ingested Posts"))
        posts_layout.addWidget(self.posts_view)

        posts_container = QWidget()
        posts_container.setLayout(posts_layout)

        panes.addWidget(posts_container, 3)

        root.addLayout(panes)

    # ========================================================
    # Event handlers
    # ========================================================

    def _on_fetch_clicked(self) -> None:
        self.controller.fetch()
        self.status_label.setText("Fetching posts...")

    def _on_extract_clicked(self) -> None:
        self.controller.extract_selected()
        self.status_label.setText("Extracting selected posts...")

    def _open_dom_review(self) -> None:
        selection = self.posts_view.selectionModel().selectedRows()
        if len(selection) != 1:
            return

        row = selection[0].row()
        post = self.posts_model.post_at(row)

        self.controller.open_dom_review(post.post_id)

    def _on_filters_changed(self) -> None:
        self.controller.set_date_range(
            self.start_date.date().toPython(),
            self.end_date.date().toPython(),
        )

        self.controller.set_whitelist(
            self.whitelist_input.text().split()
        )
        self.controller.set_blacklist(
            self.blacklist_input.text().split()
        )


    def _on_lss_progress(self, progress: LssProgress) -> None:
        msg = (
            f"Extracting {progress.completed}/{progress.total} posts"
        )
        if progress.failed:
            msg += f" ({progress.failed} failed)"

        self.status_label.setText(msg)

        # Optional: force UI repaint during long runs
        self.status_label.repaint()

    # ========================================================
    # Controller callback
    # ========================================================

    def _refresh_action_buttons(self) -> None:
        controller = self.controller

        # -----------------------------------------
        # Extract button
        # -----------------------------------------
        can_extract = any(
            p.post_id in controller.included_post_ids
            and p.state == IngestState.INGESTED
            for p in controller.posts
        )
        self.extract_button.setEnabled(can_extract)

        # -----------------------------------------
        # Open DOM Review button
        # -----------------------------------------
        selection = self.posts_view.selectionModel().selectedRows()
        if len(selection) != 1:
            self.open_dom_button.setEnabled(False)
            return

        row = selection[0].row()
        post = self.posts_model.post_at(row)

        self.open_dom_button.setEnabled(
            controller.is_extracted(post.post_id)
        )

    def _refresh_views(self) -> None:
        self.sources_model.refresh()
        self.posts_model.refresh()

        self.status_label.setText(
            f"{len(self.controller.filtered_posts())} posts visible"
        )

        # Always recompute action state
        self._refresh_action_buttons()
