# src/sitrepc2/lss/phrases.py
from __future__ import annotations

import sqlite3
from pathlib import Path

import holmes_extractor as holmes

from sitrepc2.config.paths import lexicon_path as lexicon_db_path


def _open_lexicon_db() -> sqlite3.Connection:
    path: Path = lexicon_db_path()
    if not path or not path.exists():
        raise FileNotFoundError(
            "Unable to locate lexicon.db. Have you run 'sitrepc2 init'?"
        )
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def register_search_phrases(manager: holmes.Manager) -> None:
    """
    Register Holmes search phrases from lexicon.db.

    Contract:
    - Emits EventMatch only
    - No location logic
    - No context logic
    - No role inference
    - No semantic classification
    """

    reg = manager.register_search_phrase

    with _open_lexicon_db() as conn:
        cur = conn.cursor()

        # -------------------------------------------------
        # Event phrases
        # -------------------------------------------------
        cur.execute(
            "SELECT label, phrase FROM event_phrases ORDER BY label"
        )
        for row in cur.fetchall():
            reg(
                row["phrase"],
                label=row["label"],
            )

        # # -------------------------------------------------
        # # Context phrases
        # # -------------------------------------------------
        # cur.execute(
        #     "SELECT label, phrase FROM context_phrases ORDER BY label"
        # )
        # for row in cur.fetchall():
        #     reg(
        #         row["phrase"],
        #         label=row["label"],
        #     )
