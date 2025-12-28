# location_ws.py
from __future__ import annotations

from PySide6.QtWidgets import QWidget, QHBoxLayout

from widgets.loc_search_panel import LocationSearchPanel
from widgets.loc_form import LocationForm


class LocationWorkspace(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.search_panel = LocationSearchPanel(self)
        self.form = LocationForm(self)

        layout = QHBoxLayout(self)
        layout.addWidget(self.search_panel, 1)
        layout.addWidget(self.form, 2)
        self.setLayout(layout)

        # Wiring
        self.search_panel.locationSelected.connect(self.form.load_location)
        self.search_panel.createRequested.connect(self.form.enter_create_mode)

        self.form.locationCreated.connect(self._on_location_created)

    def _on_location_created(self, location_id: int) -> None:
        # reload search + select new record
        self.search_panel._run_search(self.search_panel.search_edit.text())
        self.form.load_location(location_id)
