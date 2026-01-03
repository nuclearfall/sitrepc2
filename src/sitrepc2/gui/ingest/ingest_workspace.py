from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QDate, Signal
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

        bg = STATE_COLOR.get(row.state)

        for col, item in enumerate(items):
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            if bg:
                item.setBackground(bg)
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
