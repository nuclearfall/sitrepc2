from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QListView,
    QTreeView,
    QPushButton,
    QLabel,
    QMessageBox,
    QSizePolicy,
)

from sitrepc2.dom.dom_report import ReportNode
from sitrepc2.gui.dom.dom_controller import DomReviewController
from sitrepc2.gui.dom.report_tree_model import ReportTreeModel
from sitrepc2.gui.dom.post_list_model import PostListModel
from sitrepc2.gui.dom.detail_adapter import build_detail_payload


# ============================================================
# DOM REVIEW WORKSPACE
# ============================================================

class DomReviewWorkspace(QWidget):
    """
    Workspace for DOM review.

    Assembles:
    - Post list
    - DOM tree
    - Detail pane
    - Process / Commit actions

    Contains no domain logic.
    """

    def __init__(
        self,
        *,
        ingest_post_id: int,
        on_done: callable,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._on_done = on_done

        # ----------------------------------------------------
        # Widgets
        # ----------------------------------------------------

        self.post_list = QListView()
        self.tree_view = QTreeView()

        self.detail_title = QLabel("Inspection")
        self.detail_body = QLabel("Select a node to inspect.")
        self.detail_body.setWordWrap(True)

        self.process_button = QPushButton("Process")
        self.commit_button = QPushButton("Commit")

        self.status_label = QLabel("")
        self.status_label.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Preferred
        )

        # ----------------------------------------------------
        # Layout
        # ----------------------------------------------------

        self._init_layout()

        # ----------------------------------------------------
        # Controller (initialized later)
        # ----------------------------------------------------

        self._controller: Optional[DomReviewController] = None

        # Initial state
        self.process_button.setEnabled(False)
        self.commit_button.setEnabled(False)

        # ----------------------------------------------------
        # Signals
        # ----------------------------------------------------

        self.process_button.clicked.connect(self._on_process_clicked)
        self.commit_button.clicked.connect(self._on_commit_clicked)

        self.post_list.clicked.connect(self._on_post_focused)
        self.tree_view.clicked.connect(self._on_tree_node_selected)

    # ========================================================
    # Public API
    # ========================================================

    def load_posts(self, posts: list[ReportNode]) -> None:
        """
        Load DOM report nodes into the review workspace.
        """

        self._controller = DomReviewController(
            posts=posts,
            on_warning=self._show_warning,
            on_models_updated=self._update_models,
        )

        self.process_button.setEnabled(True)
        self.commit_button.setEnabled(False)
        self.status_label.setText("Initial review")

    # ========================================================
    # Layout
    # ========================================================

    def _init_layout(self) -> None:
        root = QVBoxLayout(self)

        # ---- Command bar ----
        cmd_bar = QHBoxLayout()
        cmd_bar.addWidget(self.process_button)
        cmd_bar.addWidget(self.commit_button)
        cmd_bar.addWidget(self.status_label)

        root.addLayout(cmd_bar)

        # ---- Main panes ----
        panes = QHBoxLayout()

        panes.addWidget(self.post_list, 1)
        panes.addWidget(self.tree_view, 3)

        detail = QVBoxLayout()
        detail.addWidget(self.detail_title)
        detail.addWidget(self.detail_body)

        detail_container = QWidget()
        detail_container.setLayout(detail)
        detail_container.setMinimumWidth(300)

        panes.addWidget(detail_container, 2)

        root.addLayout(panes)

    # ========================================================
    # Controller callbacks
    # ========================================================

    def _update_models(
        self,
        post_model: PostListModel,
        tree_model: ReportTreeModel,
    ) -> None:
        self.post_list.setModel(post_model)
        self.tree_view.setModel(tree_model)
        self.tree_view.expandAll()

        self._refresh_action_buttons()

    def _show_warning(self, message: str) -> None:
        QMessageBox.warning(self, "Warning", message)

    # ========================================================
    # UI Events
    # ========================================================

    def _on_process_clicked(self) -> None:
        if not self._controller:
            return

        self._controller.process()
        self.status_label.setText("Final review")

    def _on_commit_clicked(self) -> None:
        if not self._controller:
            return

        report = self._controller.report

        # Hard eligibility check (should already gate button)
        if not report.has_commit_eligible_event():
            return

        # Soft check: unresolved locations
        if report.has_unresolved_locations():
            reply = QMessageBox.warning(
                self,
                "Unresolved locations",
                (
                    "Some locations are unresolved.\n\n"
                    "They will be omitted from the commit.\n\n"
                    "Do you want to proceed?"
                ),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        self._controller.commit()
        self.status_label.setText("Committed")

        # Return to ingest workspace
        self._on_done()

    def _on_post_focused(self) -> None:
        # Tree model already reflects shared state
        pass

    def _on_tree_node_selected(self, index) -> None:
        node = index.internalPointer()
        payload = build_detail_payload(node)
        self._render_detail(payload)

    # ========================================================
    # Button state management
    # ========================================================

    def _refresh_action_buttons(self) -> None:
        if not self._controller:
            self.commit_button.setEnabled(False)
            return

        report = self._controller.report

        self.commit_button.setEnabled(
            report.has_commit_eligible_event()
        )

    # ========================================================
    # Detail rendering (temporary text-based)
    # ========================================================

    def _render_detail(self, payload: dict) -> None:
        """
        Temporary textual renderer.
        """

        lines = [
            f"Type: {payload['node_type']}",
            f"Summary: {payload['summary']}",
            f"Selected: {payload['selected']}",
            f"Review stage: {payload['review_stage']}",
            "",
            "Inspection:",
        ]

        insp = payload.get("inspection", {})
        for k, v in insp.items():
            lines.append(f"  {k}: {v}")

        self.detail_body.setText("\n".join(lines))
