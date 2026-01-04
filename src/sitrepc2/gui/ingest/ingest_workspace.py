from __future__ import annotations

from typing import Optional, List
from datetime import timedelta

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
        self._init_filter_date_bounds()
        self._load_posts()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # ==============================================================
        # TOOLBAR (FETCH / EXECUTION)
        # ==============================================================

        toolbar = QHBoxLayout()

        self.btn_enable = QPushButton("Enable")
        self.btn_disable = QPushButton("Disable")
        self.btn_remove = QPushButton("Remove")

        self.fetch_from = QDateEdit()
        self.fetch_to = QDateEdit()
        self.force_check = QCheckBox("Force")

        today = QDate.currentDate()
        self.fetch_from.setDate(today.addDays(-1))
        self.fetch_to.setDate(today)

        for w in (self.fetch_from, self.fetch_to):
            w.setCalendarPopup(True)
            w.setDisplayFormat("yyyy-MM-dd")

        self.btn_fetch_selected = QPushButton("Fetch Selected")
        self.btn_fetch_all = QPushButton("Fetch All Enabled")

        toolbar.addWidget(self.btn_enable)
        toolbar.addWidget(self.btn_disable)
        toolbar.addWidget(self.btn_remove)
        toolbar.addSpacing(20)
        toolbar.addWidget(QLabel("Fetch from:"))
        toolbar.addWidget(self.fetch_from)
        toolbar.addWidget(QLabel("to:"))
        toolbar.addWidget(self.fetch_to)
        toolbar.addWidget(self.force_check)
        toolbar.addSpacing(20)
        toolbar.addWidget(self.btn_fetch_selected)
        toolbar.addWidget(self.btn_fetch_all)
        toolbar.addStretch()

        root.addLayout(toolbar)

        # ==============================================================
        # FILTER ROW (POST INSPECTION)
        # ==============================================================

        filter_row = QHBoxLayout()

        self.filter_from = QDateEdit()
        self.filter_to = QDateEdit()

        for w in (self.filter_from, self.filter_to):
            w.setCalendarPopup(True)
            w.setDisplayFormat("yyyy-MM-dd")
            w.setEnabled(False)

        self.filter_from.dateChanged.connect(
            lambda _: self.filter_from.setEnabled(True)
        )
        self.filter_to.dateChanged.connect(
            lambda _: self.filter_to.setEnabled(True)
        )

        self.filter_source = QLineEdit()
        self.filter_source.setPlaceholderText("source")

        self.filter_alias = QLineEdit()
        self.filter_alias.setPlaceholderText("alias")

        self.filter_lang = QLineEdit()
        self.filter_lang.setPlaceholderText("lang")

        btn_apply_filter = QPushButton("Apply Filters")
        btn_apply_filter.clicked.connect(self._load_posts)

        filter_row.addWidget(QLabel("Filter from:"))
        filter_row.addWidget(self.filter_from)
        filter_row.addWidget(QLabel("to:"))
        filter_row.addWidget(self.filter_to)
        filter_row.addWidget(self.filter_source)
        filter_row.addWidget(self.filter_alias)
        filter_row.addWidget(self.filter_lang)
        filter_row.addWidget(btn_apply_filter)

        root.addLayout(filter_row)

        # ==============================================================
        # MAIN SPLITTER
        # ==============================================================

        splitter = QSplitter(Qt.Horizontal)

        # -------------------- Sources --------------------

        self.source_list = QListWidget()
        self.source_list.setSelectionMode(
            QAbstractItemView.ExtendedSelection
        )
        splitter.addWidget(self.source_list)

        # -------------------- Right panel --------------------

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

        # ==============================================================
        # SIGNALS
        # ==============================================================

        self.table.itemSelectionChanged.connect(self._on_post_selected)
        self.btn_fetch_selected.clicked.connect(self._fetch_selected)
        self.btn_fetch_all.clicked.connect(self._fetch_all)
        self.btn_enable.clicked.connect(lambda: self._set_active(True))
        self.btn_disable.clicked.connect(lambda: self._set_active(False))
        self.btn_remove.clicked.connect(self._remove_sources)

    # ------------------------------------------------------------------
    # SOURCES
    # ------------------------------------------------------------------

    def _load_sources(self) -> None:
        self.source_list.clear()

        for src in self.sources.load_sources():
            label = src.alias
            if not src.active:
                label += " (inactive)"

            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, src.source_name)

            if not src.active:
                item.setForeground(Qt.gray)

            self.source_list.addItem(item)

    def _selected_source_names(self) -> List[str]:
        return [
            i.data(Qt.UserRole)
            for i in self.source_list.selectedItems()
            if isinstance(i.data(Qt.UserRole), str)
        ]

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
    # FETCHING
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
        for sn in source_names:
            print(f"{source_names}")
        start_date = self.fetch_from.date().toString("yyyy-MM-dd")
        end_date = self.fetch_to.date().toString("yyyy-MM-dd")
        results = self.sources.fetch_sources(
            source_names=source_names,
            start_date=start_date,
            end_date=end_date,
            force=self.force_check.isChecked(),
        )
        print(f"Now fetching from {self.sources} for {start_date} through {end_date}")

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
    # FILTERING / POSTS
    # ------------------------------------------------------------------

    def _init_filter_date_bounds(self) -> None:
        rows = self.ingest.query_posts(IngestPostFilter())
        if not rows:
            return

        dates = [r.published_at[:10] for r in rows]
        min_q = QDate.fromString(min(dates), "yyyy-MM-dd")
        max_q = QDate.fromString(max(dates), "yyyy-MM-dd")

        self.filter_from.setMinimumDate(min_q)
        self.filter_from.setMaximumDate(max_q)
        self.filter_to.setMinimumDate(min_q)
        self.filter_to.setMaximumDate(max_q)

    def _current_filter(self) -> IngestPostFilter:
        return IngestPostFilter(
            from_date=(
                self.filter_from.date().toString("yyyy-MM-dd")
                if self.filter_from.isEnabled()
                else None
            ),
            to_date=(
                self.filter_to.date().toString("yyyy-MM-dd")
                if self.filter_to.isEnabled()
                else None
            ),
            source=self.filter_source.text().strip() or None,
            alias=self.filter_alias.text().strip() or None,
            lang=self.filter_lang.text().strip() or None,
        )

    def _load_posts(self) -> None:
        rows = self.ingest.query_posts(self._current_filter())
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
    # DETAIL / LOG
    # ------------------------------------------------------------------

    def _on_post_selected(self) -> None:
        items = self.table.selectedItems()
        if not items:
            return

        row_idx = items[0].row()
        post_id = self.ingest.query_posts(self._current_filter())[row_idx].post_id
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
