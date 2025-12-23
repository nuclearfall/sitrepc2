from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from sitrepc2.cli.init_cmd import init_workspace
from sitrepc2.gui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)

    # --------------------------------------------------
    # Pre-GUI initialization
    # --------------------------------------------------
    try:
        init_workspace()
    except Exception as exc:
        QMessageBox.critical(
            None,
            "Initialization Failed",
            f"sitrepc2 initialization failed:\n\n{exc}",
        )
        sys.exit(1)

    # --------------------------------------------------
    # Launch GUI
    # --------------------------------------------------
    window = MainWindow()
    window.show()

    sys.exit(app.exec())
