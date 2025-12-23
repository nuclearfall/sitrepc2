from __future__ import annotations

from typing import Callable, List, Optional

from sitrepc2.dom.dom_pipeline import (
    apply_spatial_coherence,
    apply_candidate_confidence,
)
from sitrepc2.dom.dom_report import ReportNode
from sitrepc2.dom.dom_persistence import persist_dom_snapshot
from sitrepc2.gui.dom.report_tree_model import ReportTreeModel
from sitrepc2.gui.dom.post_list_model import PostListModel


# ============================================================
# REVIEW STAGES
# ============================================================

REVIEW_INITIAL = "initial"
REVIEW_PROCESSED = "processed"
REVIEW_FINAL = "final"


# ============================================================
# CONTROLLER
# ============================================================

class DomReviewController:
    """
    Orchestrates DOM review lifecycle for GUI usage.

    This class:
    - coordinates pipeline steps
    - rebuilds view models
    - emits warnings via callbacks
    """

    def __init__(
        self,
        *,
        posts: List[ReportNode],
        on_warning: Optional[Callable[[str], None]] = None,
        on_models_updated: Optional[Callable[[PostListModel, ReportTreeModel], None]] = None,
    ) -> None:
        self._posts = posts
        self._review_stage = REVIEW_INITIAL

        self._on_warning = on_warning
        self._on_models_updated = on_models_updated

        self._rebuild_models()

    # --------------------------------------------------------
    # Public API (called by GUI buttons)
    # --------------------------------------------------------

    def process(self) -> None:
        """
        Apply spatial coherence + candidate confidence.

        Invoked after initial user review.
        """
        if self._review_stage != REVIEW_INITIAL:
            return

        apply_spatial_coherence(self._posts)
        apply_candidate_confidence(self._posts)

        self._review_stage = REVIEW_PROCESSED
        self._rebuild_models()

    def commit(self) -> None:
        """
        Finalize commit after final user review.

        Unresolved locations are dropped with warning.
        """
        if self._review_stage != REVIEW_PROCESSED:
            return

        if not self._has_commit_eligible_events():
            self._warn(
                "No events with resolved locations exist. "
                "Nothing will be committed."
            )
            return

        unresolved = self._count_unresolved_locations()
        if unresolved > 0:
            self._warn(
                f"{unresolved} unresolved locations will be "
                "excluded from the commit."
            )

        persist_dom_snapshot(self._posts)
        self._review_stage = REVIEW_FINAL

    # --------------------------------------------------------
    # Model access
    # --------------------------------------------------------

    @property
    def review_stage(self) -> str:
        return self._review_stage

    # --------------------------------------------------------
    # Internal helpers
    # --------------------------------------------------------

    def _rebuild_models(self) -> None:
        """
        Recreate ListView and TreeView models.
        """
        post_model = PostListModel(self._posts)
        tree_model = ReportTreeModel(self._posts)

        if self._on_models_updated:
            self._on_models_updated(post_model, tree_model)

    def _warn(self, message: str) -> None:
        if self._on_warning:
            self._on_warning(message)

    def _count_unresolved_locations(self) -> int:
        count = 0
        for post in self._posts:
            for node in post.walk():
                if node.node_type == "LOCATION":
                    if not node.inspection.get("resolved", False):
                        count += 1
        return count

    def _has_commit_eligible_events(self) -> bool:
        """
        At least one event with >=1 resolved location must exist.
        """
        for post in self._posts:
            if not post.selected:
                continue

            for node in post.walk():
                if node.node_type == "EVENT" and node.selected:
                    if any(
                        child.node_type == "LOCATION"
                        and child.inspection.get("resolved")
                        for child in node.children
                    ):
                        return True
        return False
