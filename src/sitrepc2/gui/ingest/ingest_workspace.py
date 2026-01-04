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
    QComboBox,
    QGroupBox,
    QFormLayout,
)

from sitrepc2.gui.ingest.controller import (
    IngestController,
    IngestPostFilter,
    IngestPostState,
)
from sitrepc2.gui.ingest.source_controller import (
    SourceController,
    SourceRecord,
)
from sitrepc2.gui.ingest.fetch_log_model import (
    FetchLogModel,
    FetchLogEntry,
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

    # ------------------------------------------------------------------

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.ingest = IngestController()
        self.sources = SourceController()
        self.fetch_log = FetchLogModel()

        self._editing_new = False
        self._current_source: Optional[SourceRecord] = None

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
        # TOOLBAR (FETCH)
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
        # MAIN SPLITTER
        # ==============================================================

        splitter = QSplitter(Qt.Horizontal)

        # ==============================================================
        # LEFT PANEL: Sources + Editor
        # ==============================================================

        left = QWidget()
        left_layout = QVBoxLayout(left)

        self.source_list = QListWidget()
        self.source_list.setSelectionMode(
            QAbstractItemView.ExtendedSelection
        )
        self.source_list.itemSelectionChanged.connect(
            self._on_source_selection_changed
        )
        left_layout.addWidget(QLabel("Sources"))
        left_layout.addWidget(self.source_list, stretch=1)

        # ---------------- Source Editor ----------------

        editor_box = QGroupBox("Source Editor")
        editor_layout = QFormLayout(editor_box)

        self.ed_source_name = QLineEdit()
        self.ed_alias = QLineEdit()

        self.ed_kind = QComboBox()
        self.ed_kind.addItems(["TELEGRAM", "FACEBOOK", "TWITTER", "HTTP"])

        self.ed_lang = QLineEdit()
        self.ed_active = QCheckBox("Active")

        editor_layout.addRow("Source Name", self.ed_source_name)
        editor_layout.addRow("Alias", self.ed_alias)
        editor_layout.addRow("Kind", self.ed_kind)
        editor_layout.addRow("Language", self.ed_lang)
        editor_layout.addRow("", self.ed_active)

        btn_row = QHBoxLayout()
        self.btn_new = QPushButton("New")
        self.btn_save = QPushButton("Save")
        self.btn_revert = QPushButton("Revert")
        self.btn_delete = QPushButton("Delete")

        btn_row.addWidget(self.btn_new)
        btn_row.addWidget(self.btn_save)
        btn_row.addWidget(self.btn_revert)
        btn_row.addWidget(self.btn_delete)

        editor_layout.addRow(btn_row)

        left_layout.addWidget(editor_box)

        splitter.addWidget(left)

        # ==============================================================
        # RIGHT PANEL: Posts + Detail
        # ==============================================================

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

        self.btn_fetch_selected.clicked.connect(self._fetch_selected)
        self.btn_fetch_all.clicked.connect(self._fetch_all)
        self.btn_enable.clicked.connect(lambda: self._set_active(True))
        self.btn_disable.clicked.connect(lambda: self._set_active(False))
        self.btn_remove.clicked.connect(self._remove_sources)

        self.btn_new.clicked.connect(self._new_source)
        self.btn_save.clicked.connect(self._save_source)
        self.btn_revert.clicked.connect(self._revert_source)
        self.btn_delete.clicked.connect(self._delete_source)

        self.table.itemSelectionChanged.connect(self._on_post_selected)

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
            item.setData(Qt.UserRole, src)
            if not src.active:
                item.setForeground(Qt.gray)

            self.source_list.addItem(item)

    def _on_source_selection_changed(self) -> None:
        items = self.source_list.selectedItems()

        if len(items) != 1:
            self._clear_editor(disabled=True)
            return

        src: SourceRecord = items[0].data(Qt.UserRole)
        self._load_source_into_editor(src)

    # ------------------------------------------------------------------
    # SOURCE EDITOR
    # ------------------------------------------------------------------

    def _clear_editor(self, disabled: bool = False) -> None:
        for w in (
            self.ed_source_name,
            self.ed_alias,
            self.ed_kind,
            self.ed_lang,
            self.ed_active,
        ):
            w.setEnabled(not disabled)
            if hasattr(w, "clear"):
                w.clear()

        self.ed_active.setChecked(False)
        self._current_source = None
        self._editing_new = False

    def _load_source_into_editor(self, src: SourceRecord) -> None:
        self._current_source = src
        self._editing_new = False

        self.ed_source_name.setText(src.source_name)
        self.ed_source_name.setEnabled(False)

        self.ed_alias.setText(src.alias)
        self.ed_kind.setCurrentText(src.source_kind)
        self.ed_kind.setEnabled(False)
        self.ed_lang.setText(src.source_lang)
        self.ed_active.setChecked(src.active)

    def _new_source(self) -> None:
        self._editing_new = True
        self._current_source = None

        self.ed_source_name.setEnabled(True)
        self.ed_kind.setEnabled(True)

        self.ed_source_name.clear()
        self.ed_alias.clear()
        self.ed_lang.clear()
        self.ed_active.setChecked(True)

    def _save_source(self) -> None:
        try:
            if self._editing_new:
                record = SourceRecord(
                    source_name=self.ed_source_name.text().strip(),
                    alias=self.ed_alias.text().strip(),
                    source_kind=self.ed_kind.currentText(),
                    source_lang=self.ed_lang.text().strip(),
                    active=self.ed_active.isChecked(),
                )
                self.sources.add_source(record)
            else:
                if not self._current_source:
                    return

                self.sources.update_source(
                    self._current_source.source_name,
                    alias=self.ed_alias.text().strip(),
                    source_lang=self.ed_lang.text().strip(),
                    active=self.ed_active.isChecked(),
                )

            self._load_sources()
            self._clear_editor()

        except Exception as exc:
            QMessageBox.critical(self, "Source Error", str(exc))

    def _revert_source(self) -> None:
        if self._current_source:
            self._load_source_into_editor(self._current_source)

    def _delete_source(self) -> None:
        if not self._current_source:
            return

        if QMessageBox.question(
            self,
            "Delete Source",
            "Mark this source as inactive?",
        ) == QMessageBox.Yes:
            self.sources.remove_source(self._current_source.source_name)
            self._load_sources()
            self._clear_editor()

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

    def _selected_source_names(self) -> List[str]:
        return [
            i.data(Qt.UserRole).source_name
            for i in self.source_list.selectedItems()
        ]

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
    # POSTS / FILTERING
    # ------------------------------------------------------------------

    def _init_filter_date_bounds(self) -> None:
        rows = self.ingest.query_posts(IngestPostFilter())
        if not rows:
            return

        dates = [r.published_at[:10] for r in rows]
        self._min_date = QDate.fromString(min(dates), "yyyy-MM-dd")
        self._max_date = QDate.fromString(max(dates), "yyyy-MM-dd")

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
    # DETAIL / LOG
    # ------------------------------------------------------------------

    def _on_post_selected(self) -> None:
        items = self.table.selectedItems()
        if not items:
            return

        row_idx = items[0].row()
        post_id = self.ingest.query_posts(IngestPostFilter())[row_idx].post_id
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
