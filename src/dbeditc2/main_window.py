from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QTabWidget

from dbeditc2.workspaces.gazetteer_ws import GazetteerWorkspace


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("dbeditc2")

        self._tabs = QTabWidget(self)
        self.setCentralWidget(self._tabs)

        gazetteer = GazetteerWorkspace(self)
        gazetteer.statusMessage.connect(self.statusBar().showMessage)

        self._tabs.addTab(gazetteer, "Gazetteer")
