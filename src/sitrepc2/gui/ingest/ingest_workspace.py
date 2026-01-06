from __future__ import annotations

from typing import Optional, List

from PySide6.QtCore import Qt, QDate, QThread, Signal, QObject, Slot
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

from sitrepc2.lss.pipeline import run_lss_pipeline

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
# LSS Worker (QObject — CORRECT PATTERN)
# ============================================================================

class LSSWorker(QObject):
    finished = Signal()
    failed = Signal(str)

    def __init__(
        self,
        posts: list[dict],
        *,
        reprocess: bool,
    ) -> None:
        super().__init__()
        self._posts = posts
        self._reprocess = reprocess

    @Slot()
    def run(self) -> None:
        try:
            run_lss_pipeline(
                self._posts,
                reprocess=self._reprocess,
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return

        self.finished.emit()


# ============================================================================
# Ingest Workspace
# ============================================================================

class IngestWorkspace(QWidget):
    extraction_completed = Signal()
    review_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.ingest = IngestController()
        self.sources = SourceController()
        self.fetch_log = FetchLogModel()

        self._editing_new = False
        self._loaded_source_name: Optional[str] = None

        self._progress: Optional[QProgressDialog] = None
        self._lss_thread: Optional[QThread] = None
        self._lss_worker: Optional[LSSWorker] = None

        self._build_ui()
        self._load_sources()
        self._load_posts()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

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

        # --------------------------------------------------------------
        # Left: Sources
        # --------------------------------------------------------------

        left = QWidget()
        left_layout = QVBoxLayout(left)

        left_layout.addWidget(QLabel("Sources"))
        self.source_list = QListWidget()
        self.source_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.source_list.itemSelectionChanged.connect(
            self._on_source_selection_changed
        )
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

        for b in (self.btn_new, self.btn_save, self.btn_revert, self.btn_delete):
            btn_row.addWidget(b)

        form.addRow(btn_row)
        left_layout.addWidget(editor_box)

        splitter.addWidget(left)

        # --------------------------------------------------------------
        # Right: Posts
        # --------------------------------------------------------------

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

        extract_bar = QHBoxLayout()
        self.chk_reprocess = QCheckBox("Reprocess")
        self.btn_extract = QPushButton("Extract Events")
        self.btn_extract.setEnabled(False)

        extract_bar.addWidget(self.chk_reprocess)
        extract_bar.addWidget(self.btn_extract)
        extract_bar.addStretch()

        right_layout.addLayout(extract_bar)

        self.tabs = QTabWidget()
        self.post_detail = QTextEdit(readOnly=True)
        self.fetch_log_view = QTextEdit(readOnly=True)
        self.tabs.addTab(self.post_detail, "Post Detail")
        self.tabs.addTab(self.fetch_log_view, "Fetch Log")
        right_layout.addWidget(self.tabs)

        splitter.addWidget(right)
        splitter.setStretchFactor(1, 3)
        root.addWidget(splitter)

        # --------------------------------------------------------------
        # Wiring
        # --------------------------------------------------------------

        self.btn_extract.clicked.connect(self._extract_selected_posts)

    # ------------------------------------------------------------------
    # Extraction (thread-safe)
    # ------------------------------------------------------------------

    def _extract_selected_posts(self) -> None:
        rows = self.ingest.query_posts(IngestPostFilter())

        post_ids = sorted({
            rows[item.row()].post_id
            for item in self.table.selectedItems()
        })

        if not post_ids:
            return

        posts: list[dict] = []
        for row in rows:
            if row.post_id in post_ids:
                detail = self.ingest.get_post(row.post_id)
                posts.append({
                    "id": row.post_id,
                    "text": detail.text,
                })

        if not posts:
            return

        self.btn_extract.setEnabled(False)

        self._progress = QProgressDialog(
            "Extracting events…",
            None,
            0,
            0,
            self,
        )
        self._progress.setWindowModality(Qt.NonModal)
        self._progress.setMinimumDuration(0)
        self._progress.show()

        # --- Thread + worker (canonical Qt pattern) ---
        self._lss_thread = QThread(self)
        self._lss_worker = LSSWorker(
            posts,
            reprocess=self.chk_reprocess.isChecked(),
        )
        self._lss_worker.moveToThread(self._lss_thread)

        self._lss_thread.started.connect(self._lss_worker.run)
        self._lss_worker.finished.connect(self._lss_thread.quit)
        self._lss_worker.finished.connect(self._lss_worker.deleteLater)
        self._lss_thread.finished.connect(self._lss_thread.deleteLater)

        self._lss_worker.finished.connect(self._on_extract_finished)
        self._lss_worker.failed.connect(self._on_extract_failed)

        self._lss_thread.start()

    def _on_extract_finished(self) -> None:
        if self._progress:
            self._progress.close()
            self._progress = None

        self.btn_extract.setEnabled(True)
        self._load_posts()
        self.review_requested.emit()

    def _on_extract_failed(self, message: str) -> None:
        if self._progress:
            self._progress.close()
            self._progress = None

        self.btn_extract.setEnabled(True)
        QMessageBox.critical(self, "LSS Extraction Failed", message)

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
        for c, item in enumerate(items):
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row_idx, c, item)

    def _on_post_selected(self) -> None:
        items = self.table.selectedItems()
        if not items:
            self.btn_extract.setEnabled(False)
            self.post_detail.clear()
            return

        self.btn_extract.setEnabled(True)
        rows = self.ingest.query_posts(IngestPostFilter())
        detail = self.ingest.get_post(rows[items[0].row()].post_id)
        self.post_detail.setPlainText(detail.text)
