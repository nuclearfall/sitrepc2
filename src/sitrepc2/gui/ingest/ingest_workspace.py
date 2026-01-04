from __future__ import annotations

from typing import Optional, List

from PySide6.QtCore import Qt, QDate, QThread, Signal, QObject
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
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
    QLineEdit,
    QProgressDialog,
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

# from sitrepc2.lss.pipeline import (
#     run_lss_pipeline,
#     build_holmes_and_nlp,
# )


# ============================================================================
# LSS Worker
# ============================================================================
class LSSWorker(QObject):
    progress = Signal(int, int)
    finished = Signal()
    failed = Signal(str)

    def __init__(self, ingest_posts: list[dict], reprocess: bool):
        super().__init__()
        self.ingest_posts = ingest_posts
        self.reprocess = reprocess

    def run(self):
        try:
            # IMPORTANT: import INSIDE thread
            from sitrepc2.lss.pipeline import (
                run_lss_pipeline,
                build_holmes_and_nlp,
            )

            manager = build_holmes_and_nlp()

            total = len(self.ingest_posts)
            for idx, post in enumerate(self.ingest_posts, start=1):
                self.progress.emit(idx, total)
                run_lss_pipeline(
                    ingest_posts=[post],
                    manager=manager,
                    reprocess=self.reprocess,
                )

            self.finished.emit()

        except Exception as exc:
            self.failed.emit(str(exc))

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


# ============================================================================
# Ingest Workspace
# ============================================================================

class IngestWorkspace(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.ingest = IngestController()
        self.sources = SourceController()
        self.fetch_log = FetchLogModel()

        self._editing_new = False
        self._loaded_source_name: Optional[str] = None

        self._nlp_manager = None
        self._nlp_thread: Optional[QThread] = None
        self._progress: Optional[QProgressDialog] = None

        self._build_ui()
        self._load_sources()
        self._load_posts()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # ==============================================================
        # Toolbar (fetch)
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

        splitter = QSplitter(Qt.Horizontal)

        # ==============================================================
        # Left: Sources + editor
        # ==============================================================

        left = QWidget()
        left_layout = QVBoxLayout(left)

        left_layout.addWidget(QLabel("Sources"))
        self.source_list = QListWidget()
        self.source_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.source_list.itemSelectionChanged.connect(self._on_source_selection_changed)
        left_layout.addWidget(self.source_list, stretch=1)

        editor_box = QGroupBox("Source Editor")
        form = QFormLayout(editor_box)

        self.ed_source_name = QLineEdit()
        self.ed_alias = QLineEdit()
        self.ed_kind = QComboBox()
        self.ed_kind.addItems(["TELEGRAM", "FACEBOOK", "TWITTER", "HTTP"])
        self.ed_lang = QLineEdit()
        self.ed_active = QCheckBox("Active")

        form.addRow("Source Name", self.ed_source_name)
        form.addRow("Alias", self.ed_alias)
        form.addRow("Kind", self.ed_kind)
        form.addRow("Language", self.ed_lang)
        form.addRow("", self.ed_active)

        btn_row = QHBoxLayout()
        self.btn_new = QPushButton("New")
        self.btn_save = QPushButton("Save")
        self.btn_revert = QPushButton("Revert")
        self.btn_delete = QPushButton("Delete")

        btn_row.addWidget(self.btn_new)
        btn_row.addWidget(self.btn_save)
        btn_row.addWidget(self.btn_revert)
        btn_row.addWidget(self.btn_delete)

        form.addRow(btn_row)
        left_layout.addWidget(editor_box)

        splitter.addWidget(left)

        # ==============================================================
        # Right: posts + NLP
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
        self.table.itemSelectionChanged.connect(self._on_post_selected)
        right_layout.addWidget(self.table)

        # NLP controls
        nlp_bar = QHBoxLayout()
        self.chk_reprocess = QCheckBox("Reprocess")
        self.btn_extract = QPushButton("Extract Events")
        self.btn_extract.setEnabled(False)
        nlp_bar.addWidget(self.chk_reprocess)
        nlp_bar.addWidget(self.btn_extract)
        nlp_bar.addStretch()
        right_layout.addLayout(nlp_bar)

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
        # Wiring
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

        self.btn_extract.clicked.connect(self._extract_selected_posts)

    # ------------------------------------------------------------------
    # NLP
    # ------------------------------------------------------------------

    def _ensure_nlp_manager(self):
        if self._nlp_manager is None:
            self._nlp_manager = build_holmes_and_nlp()

    def _selected_ingest_posts(self) -> List[dict]:
        rows = self.ingest.query_posts(IngestPostFilter())
        selected_rows = {i.row() for i in self.table.selectedItems()}

        out = []
        for idx in selected_rows:
            row = rows[idx]
            out.append(
                {
                    "id": row.post_id,
                    "text": self.ingest.get_post(row.post_id).text,
                }
            )
        return out

    def _extract_selected_posts(self) -> None:
        ingest_posts = self._selected_ingest_posts()
        if not ingest_posts:
            return

        self._ensure_nlp_manager()

        self.btn_extract.setEnabled(False)

        self._progress = QProgressDialog(
            "Extracting events…", None, 0, len(ingest_posts), self
        )
        self._progress.setWindowModality(Qt.ApplicationModal)
        self._progress.setMinimumDuration(0)
        self._progress.show()

        self._nlp_thread = QThread()
        worker = LSSWorker(
            ingest_posts=ingest_posts,
            reprocess=self.chk_reprocess.isChecked(),
        )
        worker.moveToThread(self._nlp_thread)

        self._nlp_thread.started.connect(worker.run)
        worker.progress.connect(self._on_extract_progress)
        worker.finished.connect(self._on_extract_finished)
        worker.failed.connect(self._on_extract_failed)

        worker.finished.connect(self._nlp_thread.quit)
        worker.failed.connect(self._nlp_thread.quit)

        self._nlp_thread.start()

    def _on_extract_progress(self, current: int, total: int):
        if self._progress:
            self._progress.setMaximum(total)
            self._progress.setValue(current)

    def _on_extract_finished(self):
        if self._progress:
            self._progress.close()
        self.btn_extract.setEnabled(False)
        self._load_posts()

    def _on_extract_failed(self, message: str):
        if self._progress:
            self._progress.close()
        QMessageBox.critical(self, "NLP Extraction Failed", message)

    # ------------------------------------------------------------------
    # Sources list
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

    def _selected_sources(self) -> List[SourceRecord]:
        out: List[SourceRecord] = []
        for i in self.source_list.selectedItems():
            src = i.data(Qt.UserRole)
            if isinstance(src, SourceRecord):
                out.append(src)
        return out

    def _selected_source_names(self) -> List[str]:
        return [s.source_name for s in self._selected_sources()]

    def _on_source_selection_changed(self) -> None:
        items = self._selected_sources()
        if len(items) == 1:
            self._load_source_into_editor(items[0])
        else:
            # No disabling: just clear the loaded identity so Save behaves as "New" only if user hit New.
            self._loaded_source_name = None

    # ------------------------------------------------------------------
    # Source editor helpers
    # ------------------------------------------------------------------

    def _clear_editor_fields(self) -> None:
        # IMPORTANT: do NOT call self.ed_kind.clear() (it would remove combo items)
        self.ed_source_name.setText("")
        self.ed_alias.setText("")
        self.ed_lang.setText("")
        self.ed_active.setChecked(True)
        self.ed_kind.setCurrentIndex(0)

        self._editing_new = False
        self._loaded_source_name = None

    def _load_source_into_editor(self, src: SourceRecord) -> None:
        self._editing_new = False
        self._loaded_source_name = src.source_name

        self.ed_source_name.setText(src.source_name)
        self.ed_alias.setText(src.alias)
        self.ed_kind.setCurrentText(src.source_kind)
        self.ed_lang.setText(src.source_lang)
        self.ed_active.setChecked(src.active)

    def _new_source(self) -> None:
        self._editing_new = True
        self._loaded_source_name = None
        self._clear_editor_fields()
        self._editing_new = True  # reassert

    def _revert_source(self) -> None:
        if not self._loaded_source_name:
            return
        # Reload from disk to avoid stale UI state
        for s in self.sources.load_sources():
            if s.source_name == self._loaded_source_name:
                self._load_source_into_editor(s)
                return

    def _save_source(self) -> None:
        try:
            record = SourceRecord(
                source_name=self.ed_source_name.text().strip(),
                alias=self.ed_alias.text().strip(),
                source_kind=self.ed_kind.currentText().strip(),
                source_lang=self.ed_lang.text().strip(),
                active=self.ed_active.isChecked(),
            )

            if not record.source_name:
                raise ValueError("source_name is required")
            if not record.alias:
                raise ValueError("alias is required")
            if not record.source_lang:
                raise ValueError("source_lang is required")
            if not record.source_kind:
                raise ValueError("source_kind is required")

            if self._editing_new or not self._loaded_source_name:
                # add
                self.sources.add_source(record)
            else:
                # replace (allows renaming and kind changes)
                self.sources.replace_source(self._loaded_source_name, record)

            self._load_sources()
            self._clear_editor_fields()

        except Exception as exc:
            QMessageBox.critical(self, "Source Error", str(exc))

    def _delete_source(self) -> None:
        if not self._loaded_source_name:
            return

        if QMessageBox.question(
            self,
            "Delete Source",
            "Hard delete this source from sources.jsonl?",
        ) != QMessageBox.Yes:
            return

        try:
            self.sources.delete_source_hard(self._loaded_source_name)
            self._load_sources()
            self._clear_editor_fields()
        except Exception as exc:
            QMessageBox.critical(self, "Delete Error", str(exc))

    # ------------------------------------------------------------------
    # Enable/Disable/Remove toolbar ops
    # ------------------------------------------------------------------

    def _set_active(self, active: bool) -> None:
        names = self._selected_source_names()
        if not names:
            return
        self.sources.set_active(names, active)
        self._load_sources()

    def _remove_sources(self) -> None:
        # Per your new requirement, "deletes should be hard deletes" — so Remove = hard delete.
        names = self._selected_source_names()
        if not names:
            return

        if QMessageBox.question(
            self,
            "Remove Sources",
            "Hard delete selected sources from sources.jsonl?",
        ) != QMessageBox.Yes:
            return

        try:
            for name in names:
                self.sources.delete_source_hard(name)
            self._load_sources()
            self._clear_editor_fields()
        except Exception as exc:
            QMessageBox.critical(self, "Remove Error", str(exc))

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
        names = [s.source_name for s in self.sources.load_sources() if s.active]
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
    # Posts
    # ------------------------------------------------------------------

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

        # bg_hex = STATE_COLOR.get(row.state)
        # bg = QColor(bg_hex) if bg_hex else None

        for c, item in enumerate(items):
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row_idx, c, item)

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
            lines.append(f"[{e.timestamp}] {e.source_name} ({e.source_kind}) → {status}")
            if e.error:
                lines.append(f"    {e.error}")
        self.fetch_log_view.setPlainText("\n".join(lines))
