# src/dbeditc2/app.py
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from dbeditc2.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)

    window = MainWindow()
    window.resize(1200, 800)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
