# src/dbeditc2/widgets/details/gazetteer_details_view.py
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QHBoxLayout,
)

from dbeditc2.enums import CollectionKind
from dbeditc2.models import GazetteerEntityViewModel


class GazetteerDetailsView(QWidget):
    """
    Form-based details view for gazetteer entities.

    Displays entity information and related semantic lists
    (aliases, regions, groups).
    """

    aliasAddRequested = Signal(str)
    aliasRemoveRequested = Signal(str)
    regionAssignRequested = Signal()
    groupAssignRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._entity_kind: CollectionKind | None = None

        main_layout = QVBoxLayout(self)

        # --- Core fields ---
        form_layout = QFormLayout()
        main_layout.addLayout(form_layout)

        self._name_edit = QLineEdit(self)
        self._lat_edit = QLineEdit(self)
        self._lon_edit = QLineEdit(self)
        self._place_edit = QLineEdit(self)
        self._wikidata_edit = QLineEdit(self)

        form_layout.addRow("Name:", self._name_edit)
        form_layout.addRow("Latitude:", self._lat_edit)
        form_layout.addRow("Longitude:", self._lon_edit)
        form_layout.addRow("Place type:", self._place_edit)
        form_layout.addRow("Wikidata ID:", self._wikidata_edit)

        # --- Aliases ---
        main_layout.addWidget(QLabel("Aliases:", self))
        self._aliases_list = QListWidget(self)
        main_layout.addWidget(self._aliases_list)
        self._aliases_list.setSelectionMode(QListWidget.SingleSelection)


        alias_controls = QHBoxLayout()
        self._alias_input = QLineEdit(self)
        self._alias_input.setPlaceholderText("Add alias…")
        self._alias_add_btn = QPushButton("Add", self)

        alias_controls.addWidget(self._alias_input)
        alias_controls.addWidget(self._alias_add_btn)
        main_layout.addLayout(alias_controls)

        self._alias_add_btn.clicked.connect(
            lambda: self.aliasAddRequested.emit(self._alias_input.text())
        )
        self._alias_remove_btn = QPushButton("Remove", self)
        self._alias_remove_btn.clicked.connect(self._on_remove_alias)

        # --- Regions ---
        main_layout.addWidget(QLabel("Regions:", self))
        self._regions_list = QListWidget(self)
        main_layout.addWidget(self._regions_list)

        self._assign_region_btn = QPushButton("Assign region", self)
        self._assign_region_btn.clicked.connect(self.regionAssignRequested)
        main_layout.addWidget(self._assign_region_btn)

        # --- Groups ---
        main_layout.addWidget(QLabel("Groups:", self))
        self._groups_list = QListWidget(self)
        main_layout.addWidget(self._groups_list)

        self._assign_group_btn = QPushButton("Assign group", self)
        self._assign_group_btn.clicked.connect(self.groupAssignRequested)
        main_layout.addWidget(self._assign_group_btn)

    def set_entity_type(self, kind: CollectionKind) -> None:
        """
        Set the type of gazetteer entity being displayed.
        """
        self._entity_kind = kind

    def set_entity_data(self, data: GazetteerEntityViewModel) -> None:
        """
        Populate the form with entity data.
        """
        self._name_edit.setText(data.name or "")
        self._lat_edit.setText("" if data.latitude is None else str(data.latitude))
        self._lon_edit.setText("" if data.longitude is None else str(data.longitude))
        self._place_edit.setText(data.place_type or "")
        self._wikidata_edit.setText(data.wikidata_id or "")

        self._aliases_list.clear()
        if data.aliases:
            self._aliases_list.addItems(data.aliases)

        self._regions_list.clear()
        if data.regions:
            self._regions_list.addItems(data.regions)

        self._groups_list.clear()
        if data.groups:
            self._groups_list.addItems(data.groups)

        self.set_read_only(data.is_read_only)

    def set_read_only(self, read_only: bool) -> None:
        """
        Set fields to read-only mode.
        """
        for widget in (
            self._name_edit,
            self._lat_edit,
            self._lon_edit,
            self._place_edit,
            self._wikidata_edit,
            self._alias_input,
        ):
            widget.setReadOnly(read_only)

        self._alias_add_btn.setEnabled(not read_only)
        self._assign_region_btn.setEnabled(not read_only)
        self._assign_group_btn.setEnabled(not read_only)

    def clear(self) -> None:
        """
        Clear all displayed data.
        """
        self._name_edit.clear()
        self._lat_edit.clear()
        self._lon_edit.clear()
        self._place_edit.clear()
        self._wikidata_edit.clear()
        self._aliases_list.clear()
        self._regions_list.clear()
        self._groups_list.clear()

    def _on_remove_alias(self):
        items = self._aliases_list.selectedItems()
        if items:
            self.aliasRemoveRequested.emit(items[0].text())

