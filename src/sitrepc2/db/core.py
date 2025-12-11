# src/sitrepc2/db/core.py
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from sitrepc2.config.paths import current_db_path


def connect() -> sqlite3.Connection:
    """
    Open a connection to the SQLite database located in the current project's
    .sitrepc2/ directory. Foreign keys are enabled automatically.
    """
    db_file = current_db_path()
    conn = sqlite3.connect(db_file)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    """
    Context manager that returns a writable DB connection.

    Usage:
        with get_conn() as conn:
            conn.execute("INSERT ...")
    """
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
