from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QDialog

from .ui.model_validator_dialog import ModelValidatorDialog
from .main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)

    # ------------------------------------------------------------
    # Validate spaCy / coreferee models before starting UI
    # ------------------------------------------------------------
    validator = ModelValidatorDialog()
    if validator.exec() != QDialog.DialogCode.Accepted:
        return 0

    spacy_model, coreferee_enabled = validator.selected_configuration()

    # ------------------------------------------------------------
    # Launch main window with validated configuration
    # ------------------------------------------------------------
    window = MainWindow(
        spacy_model=spacy_model,
        enable_coreferee=coreferee_enabled,
    )
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
