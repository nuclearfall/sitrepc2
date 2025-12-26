# src/dbeditc2/widgets/app_toolbar.py
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QToolBar
from PySide6.QtGui import QAction

from dbeditc2.enums import EditorMode


class AppToolBar(QToolBar):
    """
    Global application toolbar.

    Emits user intent signals only.
    Does not perform validation or state decisions.
    """

    addRequested = Signal()
    editRequested = Signal()
    removeRequested = Signal()
    restoreRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._action_add = QAction("Add", self)
        self._action_edit = QAction("Edit", self)
        self._action_remove = QAction("Remove", self)
        self._action_restore = QAction("Restore", self)

        self.addAction(self._action_add)
        self.addAction(self._action_edit)
        self.addAction(self._action_remove)
        self.addAction(self._action_restore)

        self._action_add.triggered.connect(self.addRequested)
        self._action_edit.triggered.connect(self.editRequested)
        self._action_remove.triggered.connect(self.removeRequested)
        self._action_restore.triggered.connect(self.restoreRequested)

    def set_mode(self, mode: EditorMode) -> None:
        """
        Update toolbar appearance based on editor mode.
        Currently presentation-only.
        """
        # No behavior yet; reserved for future styling/enablement
        pass

    def set_actions_enabled(
        self,
        *,
        add: bool,
        edit: bool,
        remove: bool,
        restore: bool,
    ) -> None:
        """
        Enable or disable toolbar actions.
        """
        self._action_add.setEnabled(add)
        self._action_edit.setEnabled(edit)
        self._action_remove.setEnabled(remove)
        self._action_restore.setEnabled(restore)
