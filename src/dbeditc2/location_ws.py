# location_ws.py
from __future__ import annotations

from PySide6.QtWidgets import QWidget, QHBoxLayout
from PySide6.QtCore import Signal, Slot

from .widgets.loc_search_panel import LocationSearchPanel
from .widgets.loc_form import LocationForm


class LocationWorkspace(QWidget):
    # Must be str to match MainWindow expectations
    statusMessage = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.search_panel = LocationSearchPanel(self)
        self.form = LocationForm(self)

        layout = QHBoxLayout(self)
        layout.addWidget(self.search_panel, 3)
        layout.addWidget(self.form, 2)
        self.setLayout(layout)

        # ---- Wiring ----

        # Search → form
        self.search_panel.locationSelected.connect(self.form.load_location)
        self.search_panel.createRequested.connect(self.form.enter_create_mode)

        # Form → workspace
        self.form.locationCreated.connect(self._on_location_created)

        # Forward status messages upward
        self.search_panel.statusMessage.connect(self.statusMessage)
        self.form.statusMessage.connect(self.statusMessage)

    def _on_location_created(self, location_id: object) -> None:
        """
        Reload search results and select the newly created location.
        location_id is a 64-bit value and must not be truncated.
        """
        self.search_panel._run_search(self.search_panel.search_edit.text())
        self.form.load_location(location_id)


