# src/sitrepc2/gui/app.py

import sys
from PySide6.QtWidgets import QApplication

from sitrepc2.gui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
