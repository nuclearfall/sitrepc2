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

from sitrepc2.lss.pipeline import (
    run_lss_pipeline,
    build_holmes_and_nlp,
)


# ============================================================================
# LSS Worker
# ============================================================================

class LSSWorker(QObject):
    progress = Signal(int, int)   # current, total
    finished = Signal()
    failed = Signal(str)

    def __init__(self, ingest_posts: List[dict], manager, reprocess: bool):
        super().__init__()
        self.ingest_posts = ingest_posts
        self.manager = manager
        self.reprocess = reprocess

    def run(self):
        try:
            total = len(self.ingest_posts)
            for idx, post in enumerate(self.ingest_posts, start=1):
                self.progress.emit(idx, total)
                run_lss_pipeline(
                    ingest_posts=[post],
                    manager=self.manager,
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
            manager=self._nlp_manager,
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
    # (Everything else below is unchanged: sources, fetching, table, etc.)
    # ------------------------------------------------------------------

    # ... remainder identical to your previous implementation ...
