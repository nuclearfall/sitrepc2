from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QDate, Signal
from PySide6.QtGui import QColor

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QDateEdit,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
    QTextEdit,
    QSplitter,
    QListWidget,
    QListWidgetItem,
)

from sitrepc2.gui.ingest.controller import (
    IngestController,
    IngestPostFilter,
    IngestPostState,
)


# ============================================================================
# Lifecycle visuals
# ============================================================================

STATE_ICON = {
    IngestPostState.RAW: "⏺",
    IngestPostState.LSS_RUNNING: "🔄",
    IngestPostState.NO_EVENTS: "⚠",
    IngestPostState.READY_FOR_REVIEW: "🟡",
    IngestPostState.COMMITTED: "✅",
}

STATE_COLOR = {
    IngestPostState.RAW: None,
    IngestPostState.LSS_RUNNING: "#dbeafe",
    IngestPostState.NO_EVENTS: "#fef3c7",
    IngestPostState.READY_FOR_REVIEW: "#fef08a",
    IngestPostState.COMMITTED: "#dcfce7",
}


# ============================================================================
# Ingest Workspace
# ============================================================================

class IngestWorkspace(QWidget):

    postSelected = Signal(int)

    # ------------------------------------------------------------------

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.controller = IngestController()
        self._selected_post_id: Optional[int] = None

        self._build_ui()
        self._load_sources()
        self._init_date_bounds()
        self._load_posts()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)

        # --------------------------------------------------------------
        # Sources panel
        # --------------------------------------------------------------

        self.source_list = QListWidget()
        self.source_list.setFixedWidth(220)
        self.source_list.itemSelectionChanged.connect(
            self._on_source_selected
        )
        root.addWidget(self.source_list)

        # --------------------------------------------------------------
        # Right side
        # --------------------------------------------------------------

        right = QWidget()
        right_layout = QVBoxLayout(right)
        root.addWidget(right)

        # --------------------------------------------------------------
        # Filters
        # --------------------------------------------------------------

        filter_layout = QHBoxLayout()

        self.from_date = QDateEdit()
        self.from_date.setCalendarPopup(True)
        self.from_date.setDisplayFormat("yyyy-MM-dd")
        self.from_date.setEnabled(False)
        self.from_date.dateChanged.connect(
            lambda _: self.from_date.setEnabled(True)
        )

        self.to_date = QDateEdit()
        self.to_date.setCalendarPopup(True)
        self.to_date.setDisplayFormat("yyyy-MM-dd")
        self.to_date.setEnabled(False)
        self.to_date.dateChanged.connect(
            lambda _: self.to_date.setEnabled(True)
        )

        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText("source")

        self.publisher_edit = QLineEdit()
        self.publisher_edit.setPlaceholderText("publisher")

        self.alias_edit = QLineEdit()
        self.alias_edit.setPlaceholderText("alias")

        self.lang_edit = QLineEdit()
        self.lang_edit.setPlaceholderText("lang")

        apply_btn = QPushButton("Apply Filters")
        apply_btn.clicked.connect(self._load_posts)

        for w in (
            QLabel("From:"),
            self.from_date,
            QLabel("To:"),
            self.to_date,
            self.source_edit,
            self.publisher_edit,
            self.alias_edit,
            self.lang_edit,
            apply_btn,
        ):
            filter_layout.addWidget(w)

        right_layout.addLayout(filter_layout)

        # --------------------------------------------------------------
        # Splitter
        # --------------------------------------------------------------

        splitter = QSplitter(Qt.Vertical)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            [
                "State",
                "Published",
                "Alias",
                "Source",
                "Lang",
                "Events",
                "Snippet",
            ]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(
            self._on_selection_changed
        )

        splitter.addWidget(self.table)

        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setPlaceholderText(
            "Select a post to view full text…"
        )
        splitter.addWidget(self.detail)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        right_layout.addWidget(splitter)

    # ------------------------------------------------------------------
    # Sources
    # ------------------------------------------------------------------

    def _load_sources(self) -> None:
        self.source_list.clear()

        for src in self.controller.get_sources():
            label = src.alias
            if not src.active:
                label += " (inactive)"

            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, src.source_name)

            if not src.active:
                item.setForeground(Qt.gray)

            self.source_list.addItem(item)

    # ------------------------------------------------------------------
    # Filters
    # ------------------------------------------------------------------

    def _on_source_selected(self) -> None:
        items = self.source_list.selectedItems()
        if not items:
            self.source_edit.clear()
            return

        source_name = items[0].data(Qt.UserRole)
        if isinstance(source_name, str):
            self.source_edit.setText(source_name)
            self._load_posts()

    # ------------------------------------------------------------------

    def _current_filter(self) -> IngestPostFilter:
        return IngestPostFilter(
            from_date=(
                self.from_date.date().toString("yyyy-MM-dd")
                if self.from_date.isEnabled()
                else None
            ),
            to_date=(
                self.to_date.date().toString("yyyy-MM-dd")
                if self.to_date.isEnabled()
                else None
            ),
            source=self.source_edit.text().strip() or None,
            publisher=self.publisher_edit.text().strip() or None,
            alias=self.alias_edit.text().strip() or None,
            lang=self.lang_edit.text().strip() or None,
        )

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def _init_date_bounds(self) -> None:
        rows = self.controller.query_posts(IngestPostFilter())
        if not rows:
            return

        dates = [r.published_at[:10] for r in rows]
        min_q = QDate.fromString(min(dates), "yyyy-MM-dd")
        max_q = QDate.fromString(max(dates), "yyyy-MM-dd")

        if min_q.isValid() and max_q.isValid():
            self.from_date.setMinimumDate(min_q)
            self.from_date.setMaximumDate(max_q)
            self.to_date.setMinimumDate(min_q)
            self.to_date.setMaximumDate(max_q)

    # ------------------------------------------------------------------

    def _load_posts(self) -> None:
        self.table.setRowCount(0)
        self.detail.clear()
        self._selected_post_id = None

        rows = self.controller.query_posts(self._current_filter())
        self.table.setRowCount(len(rows))

        for r, row in enumerate(rows):
            self._populate_row(r, row)

        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(0, 160)

    # ------------------------------------------------------------------

    def _populate_row(self, row_idx: int, row) -> None:
        icon = STATE_ICON.get(row.state, "")
        label = row.state.value.replace("_", " ")
        text = f"{icon} {label}"

        state_item = QTableWidgetItem(text)
        state_item.setData(Qt.UserRole, row.post_id)

        items = [
            state_item,
            QTableWidgetItem(row.published_at),
            QTableWidgetItem(row.alias),
            QTableWidgetItem(row.source),
            QTableWidgetItem(row.lang),
            QTableWidgetItem(str(row.event_count)),
            QTableWidgetItem(row.text_snippet),
        ]

        bg_hex = STATE_COLOR.get(row.state)
        bg_color = QColor(bg_hex) if bg_hex else None

        for col, item in enumerate(items):
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)

            if bg_color:
                item.setBackground(bg_color)

            self.table.setItem(row_idx, col, item)


    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def _on_selection_changed(self) -> None:
        items = self.table.selectedItems()
        if not items:
            return

        post_id = items[0].data(Qt.UserRole)
        if not isinstance(post_id, int):
            return

        self._selected_post_id = post_id
        self.postSelected.emit(post_id)

        detail = self.controller.get_post(post_id)
        self.detail.setPlainText(detail.text)
from __future__ import annotations

from typing import Optional, List

from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QDateEdit,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
    QTextEdit,
    QSplitter,
    QListWidget,
    QListWidgetItem,
    QTabWidget,
    QCheckBox,
    QMessageBox,
)

from sitrepc2.gui.ingest.controller import (
    IngestController,
    IngestPostFilter,
    IngestPostState,
)
from sitrepc2.gui.ingest.source_controller import SourceController
from sitrepc2.gui.ingest.fetch_log_model import FetchLogModel, FetchLogEntry


# ============================================================================
# Lifecycle visuals
# ============================================================================

STATE_ICON = {
    IngestPostState.RAW: "⏺",
    IngestPostState.LSS_RUNNING: "🔄",
    IngestPostState.NO_EVENTS: "⚠",
    IngestPostState.READY_FOR_REVIEW: "🟡",
    IngestPostState.COMMITTED: "✅",
}

STATE_COLOR = {
    IngestPostState.RAW: None,
    IngestPostState.LSS_RUNNING: "#dbeafe",
    IngestPostState.NO_EVENTS: "#fef3c7",
    IngestPostState.READY_FOR_REVIEW: "#fef08a",
    IngestPostState.COMMITTED: "#dcfce7",
}


# ============================================================================
# Ingest Workspace
# ============================================================================

class IngestWorkspace(QWidget):

    # ------------------------------------------------------------------

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.ingest = IngestController()
        self.sources = SourceController()
        self.fetch_log = FetchLogModel()

        self._build_ui()
        self._load_sources()
        self._init_date_bounds()
        self._load_posts()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # --------------------------------------------------------------
        # Toolbar
        # --------------------------------------------------------------

        toolbar = QHBoxLayout()

        self.btn_enable = QPushButton("Enable")
        self.btn_disable = QPushButton("Disable")
        self.btn_remove = QPushButton("Remove")

        self.btn_fetch_selected = QPushButton("Fetch Selected")
        self.btn_fetch_all = QPushButton("Fetch All Enabled")

        self.force_check = QCheckBox("Force")
        self.fetch_from = QDateEdit()
        self.fetch_from.setCalendarPopup(True)
        self.fetch_from.setDisplayFormat("yyyy-MM-dd")
        self.fetch_from.setDate(QDate.currentDate())

        self.fetch_to = QDateEdit()
        self.fetch_to.setCalendarPopup(True)
        self.fetch_to.setDisplayFormat("yyyy-MM-dd")
        self.fetch_to.setDate(QDate.currentDate())

        toolbar.addWidget(self.btn_enable)
        toolbar.addWidget(self.btn_disable)
        toolbar.addWidget(self.btn_remove)
        toolbar.addSpacing(20)
        toolbar.addWidget(QLabel("From:"))
        toolbar.addWidget(self.fetch_from)
        toolbar.addWidget(QLabel("To:"))
        toolbar.addWidget(self.fetch_to)
        toolbar.addWidget(self.force_check)
        toolbar.addSpacing(20)
        toolbar.addWidget(self.btn_fetch_selected)
        toolbar.addWidget(self.btn_fetch_all)
        toolbar.addStretch()

        root.addLayout(toolbar)

        # --------------------------------------------------------------
        # Main splitter
        # --------------------------------------------------------------

        splitter = QSplitter(Qt.Horizontal)

        # Sources
        self.source_list = QListWidget()
        self.source_list.setSelectionMode(
            QAbstractItemView.ExtendedSelection
        )
        splitter.addWidget(self.source_list)

        # Right side
        right = QWidget()
        right_layout = QVBoxLayout(right)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["State", "Published", "Alias", "Source", "Lang", "Events", "Snippet"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)

        right_layout.addWidget(self.table)

        self.tabs = QTabWidget()

        self.post_detail = QTextEdit()
        self.post_detail.setReadOnly(True)

        self.fetch_log_view = QTextEdit()
        self.fetch_log_view.setReadOnly(True)

        self.tabs.addTab(self.post_detail, "Post Detail")
        self.tabs.addTab(self.fetch_log_view, "Fetch Log")

        right_layout.addWidget(self.tabs)

        splitter.addWidget(right)
        splitter.setStretchFactor(1, 3)

        root.addWidget(splitter)

        # --------------------------------------------------------------
        # Wiring
        # --------------------------------------------------------------

        self.table.itemSelectionChanged.connect(self._on_post_selected)
        self.btn_fetch_selected.clicked.connect(self._fetch_selected)
        self.btn_fetch_all.clicked.connect(self._fetch_all)
        self.btn_enable.clicked.connect(lambda: self._set_active(True))
        self.btn_disable.clicked.connect(lambda: self._set_active(False))
        self.btn_remove.clicked.connect(self._remove_sources)

    # ------------------------------------------------------------------
    # Sources
    # ------------------------------------------------------------------

    def _load_sources(self) -> None:
        self.source_list.clear()

        for src in self.sources.load_sources():
            label = f"{src.alias}"
            if not src.active:
                label += " (inactive)"

            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, src.source_name)

            if not src.active:
                item.setForeground(Qt.gray)

            self.source_list.addItem(item)

    # ------------------------------------------------------------------

    def _selected_source_names(self) -> List[str]:
        return [
            i.data(Qt.UserRole)
            for i in self.source_list.selectedItems()
            if isinstance(i.data(Qt.UserRole), str)
        ]

    # ------------------------------------------------------------------
    # Fetching
    # ------------------------------------------------------------------

    def _fetch_selected(self) -> None:
        names = self._selected_source_names()
        if not names:
            QMessageBox.information(self, "Fetch", "No sources selected.")
            return
        self._fetch(names)

    def _fetch_all(self) -> None:
        names = [
            s.source_name
            for s in self.sources.load_sources()
            if s.active
        ]
        self._fetch(names)

    def _fetch(self, source_names: List[str]) -> None:
        results = self.sources.fetch_sources(
            source_names=source_names,
            start_date=self.fetch_from.date().toString("yyyy-MM-dd"),
            end_date=self.fetch_to.date().toString("yyyy-MM-dd"),
            force=self.force_check.isChecked(),
        )

        for r in results:
            self.fetch_log.add(
                FetchLogEntry(
                    timestamp=r.timestamp,
                    source_name=r.source_name,
                    source_kind=r.source_kind,
                    start_date=r.start_date,
                    end_date=r.end_date,
                    force=r.force,
                    fetched_count=r.fetched_count,
                    error=r.error,
                )
            )

        self._refresh_fetch_log()
        self._load_posts()

    # ------------------------------------------------------------------
    # Source state
    # ------------------------------------------------------------------

    def _set_active(self, active: bool) -> None:
        names = self._selected_source_names()
        if names:
            self.sources.set_active(names, active)
            self._load_sources()

    def _remove_sources(self) -> None:
        names = self._selected_source_names()
        if not names:
            return

        if QMessageBox.question(
            self,
            "Remove Sources",
            "Mark selected sources as inactive?",
        ) == QMessageBox.Yes:
            for name in names:
                self.sources.remove_source(name)
            self._load_sources()

    # ------------------------------------------------------------------
    # Posts
    # ------------------------------------------------------------------

    def _init_date_bounds(self) -> None:
        rows = self.ingest.query_posts(IngestPostFilter())
        if not rows:
            return

        dates = [r.published_at[:10] for r in rows]
        self.fetch_from.setMinimumDate(
            QDate.fromString(min(dates), "yyyy-MM-dd")
        )
        self.fetch_to.setMaximumDate(
            QDate.fromString(max(dates), "yyyy-MM-dd")
        )

    def _load_posts(self) -> None:
        rows = self.ingest.query_posts(IngestPostFilter())
        self.table.setRowCount(len(rows))

        for r, row in enumerate(rows):
            self._populate_row(r, row)

        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(0, 160)

    def _populate_row(self, row_idx: int, row) -> None:
        icon = STATE_ICON.get(row.state, "")
        text = f"{icon} {row.state.value.replace('_', ' ')}"

        items = [
            QTableWidgetItem(text),
            QTableWidgetItem(row.published_at),
            QTableWidgetItem(row.alias),
            QTableWidgetItem(row.source),
            QTableWidgetItem(row.lang),
            QTableWidgetItem(str(row.event_count)),
            QTableWidgetItem(row.text_snippet),
        ]

        bg_hex = STATE_COLOR.get(row.state)
        bg = QColor(bg_hex) if bg_hex else None

        for c, item in enumerate(items):
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            if bg:
                item.setBackground(bg)
            self.table.setItem(row_idx, c, item)

    # ------------------------------------------------------------------
    # Detail / Log
    # ------------------------------------------------------------------

    def _on_post_selected(self) -> None:
        items = self.table.selectedItems()
        if not items:
            return

        row = items[0].row()
        post_id = self.ingest.query_posts(IngestPostFilter())[row].post_id
        detail = self.ingest.get_post(post_id)
        self.post_detail.setPlainText(detail.text)

    def _refresh_fetch_log(self) -> None:
        lines = []
        for e in self.fetch_log.entries():
            status = "ERROR" if e.error else f"{e.fetched_count} posts"
            lines.append(
                f"[{e.timestamp}] {e.source_name} ({e.source_kind}) → {status}"
            )
            if e.error:
                lines.append(f"    {e.error}")

        self.fetch_log_view.setPlainText("\n".join(lines))
