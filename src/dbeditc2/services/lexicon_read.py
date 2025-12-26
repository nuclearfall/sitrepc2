# src/dbeditc2/services/lexicon_read.py
from __future__ import annotations

import sqlite3

from sitrepc2.config.paths import lexicon_path

from dbeditc2.enums import CollectionKind
from dbeditc2.models import EntrySummary, LexiconPhraseViewModel


# ---------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------

def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(lexicon_path())
    con.row_factory = sqlite3.Row
    return con


# ---------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------

def list_phrases(kind: CollectionKind) -> list[EntrySummary]:
    """
    List lexicon phrases (event or context).
    """
    table = _table_for_kind(kind)

    with _conn() as con:
        rows = con.execute(
            f"""
            SELECT id, phrase
            FROM {table}
            ORDER BY phrase
            """
        ).fetchall()

    return [
        EntrySummary(
            entry_id=row["id"],
            display_name=row["phrase"],
            editable=False,
        )
        for row in rows
    ]


# ---------------------------------------------------------------------
# Load single phrase
# ---------------------------------------------------------------------

def load_phrase(kind: CollectionKind, phrase_id: int) -> LexiconPhraseViewModel:
    """
    Load a single lexicon phrase.
    """
    table = _table_for_kind(kind)

    with _conn() as con:
        row = con.execute(
            f"""
            SELECT phrase
            FROM {table}
            WHERE id = ?
            """,
            (phrase_id,),
        ).fetchone()

    if row is None:
        raise KeyError(f"Phrase not found: {phrase_id}")

    return LexiconPhraseViewModel(
        phrase_text=row["phrase"],
        is_event_phrase=(kind == CollectionKind.EVENT_PHRASES),
        is_read_only=True,
    )


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _table_for_kind(kind: CollectionKind) -> str:
    if kind == CollectionKind.EVENT_PHRASES:
        return "event_phrases"
    if kind == CollectionKind.CONTEXT_PHRASES:
        return "context_phrases"

    raise ValueError(f"Unsupported lexicon kind: {kind}")
