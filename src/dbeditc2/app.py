# src/dbeditc2/app.py
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from dbeditc2.main_window import MainWindow
from dbeditc2.controller.editor_controller import EditorController


def main() -> None:
    app = QApplication(sys.argv)

    window = MainWindow()
    window.resize(1200, 800)

    # ---------------------------------------------------------
    # CONTROLLER WIRING (THIS WAS MISSING)
    # ---------------------------------------------------------
    EditorController(
        navigation=window._navigation_tree,
        search=window._search_panel,
        entry_list=window._entry_list,
        details=window._details_stack,
        toolbar=window._toolbar,
    )

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
