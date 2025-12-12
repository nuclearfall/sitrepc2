# src/sitrepc2/pipeline/db.py

import sqlite3
from pathlib import Path
import json
from datetime import datetime

DB_PATH = Path(".sitrepc2/pipeline.sqlite")

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts_fetched (
    post_id        TEXT PRIMARY KEY,
    channel        TEXT,
    published_at   TEXT,
    fetched_at     TEXT,
    raw_text       TEXT,
    text           TEXT,
    source_json    TEXT
);

CREATE TABLE IF NOT EXISTS posts_processed (
    post_id     TEXT PRIMARY KEY,
    processed_at TEXT,
    pd_tree_json TEXT
);

CREATE TABLE IF NOT EXISTS posts_reviewed (
    post_id      TEXT PRIMARY KEY,
    reviewed_at  TEXT,
    pd_tree_json TEXT
);

CREATE TABLE IF NOT EXISTS posts_committed (
    post_id      TEXT PRIMARY KEY,
    committed_at TEXT,
    event_json   TEXT
);
"""

def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode = wal;")
    return conn

def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()
    return conn
