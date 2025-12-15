#!/usr/bin/env python3
"""
create_db.py

Standalone SQLite database creation script for sitrepc2.

• Creates the database if it does not exist
• Applies the full schema
• Enables foreign key enforcement
• Safe to re-run (idempotent)

This script intentionally has NO dependencies on sitrepc2 internals
so it can be used for recovery, bootstrapping, or patch-based review.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
import sys


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

----------------------------------------------------------------------
-- 1. Metadata table
----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

----------------------------------------------------------------------
-- 2. Telegram Posts
----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS posts (
    post_id        INTEGER PRIMARY KEY,
    channel        TEXT NOT NULL,
    alias          TEXT NOT NULL,
    published_at   TEXT NOT NULL,
    fetched_at     TEXT NOT NULL,
    lang           TEXT NOT NULL,
    raw_json       TEXT
);

CREATE INDEX IF NOT EXISTS idx_posts_channel_date
    ON posts(channel, published_at);

----------------------------------------------------------------------
-- 3. Post Text
----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS post_text (
    post_id      INTEGER PRIMARY KEY
                 REFERENCES posts(post_id) ON DELETE CASCADE,
    raw_text     TEXT,
    clean_text   TEXT,
    translated   INTEGER DEFAULT 0 CHECK (translated IN (0,1))
);

----------------------------------------------------------------------
-- 4. Raw Event Matches
----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS events_raw (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id      INTEGER NOT NULL
                 REFERENCES posts(post_id) ON DELETE CASCADE,
    event_json   TEXT NOT NULL,
    hash         TEXT NOT NULL UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_events_raw_post_id
    ON events_raw(post_id);

----------------------------------------------------------------------
-- 5. Domain Events
----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS events_dom (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_event_id  INTEGER NOT NULL
                  REFERENCES events_raw(id) ON DELETE CASCADE,
    dom_json      TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending','audited','final'))
);

CREATE INDEX IF NOT EXISTS idx_events_dom_status
    ON events_dom(status);

----------------------------------------------------------------------
-- 6. Location Candidates
----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS locations (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    event_dom_id   INTEGER NOT NULL
                   REFERENCES events_dom(id) ON DELETE CASCADE,
    name           TEXT NOT NULL,
    qid            TEXT,
    osm_id         TEXT,
    anchor_dir     TEXT,
    confidence     REAL,
    resolved       INTEGER DEFAULT 0 CHECK (resolved IN (0,1))
);

CREATE INDEX IF NOT EXISTS idx_locations_event
    ON locations(event_dom_id);

----------------------------------------------------------------------
-- 7. Audit Requirements
----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_requirements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_dom_id    INTEGER NOT NULL
                    REFERENCES events_dom(id) ON DELETE CASCADE,
    issue_type      TEXT NOT NULL,
    issue_json      TEXT NOT NULL,
    resolved        INTEGER DEFAULT 0 CHECK (resolved IN (0,1))
);

CREATE INDEX IF NOT EXISTS idx_audit_event
    ON audit_requirements(event_dom_id);

----------------------------------------------------------------------
-- 8. Final Events
----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS final_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    event_dom_id  INTEGER UNIQUE NOT NULL
                  REFERENCES events_dom(id) ON DELETE CASCADE,
    final_json    TEXT NOT NULL,
    committed_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_final_committed
    ON final_events(committed_at);

----------------------------------------------------------------------
-- 9. UI State
----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ui_state (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def create_db(db_path: Path, overwrite: bool = False) -> None:
    if db_path.exists():
        if overwrite:
            db_path.unlink()
        else:
            print(f"[INFO] Database already exists: {db_path}")
            return

    db_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] Creating database at {db_path}")
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()

    print("[OK] Database schema applied successfully.")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: create_db.py PATH_TO_DB [--overwrite]")
        return 1

    db_path = Path(argv[1]).expanduser().resolve()
    overwrite = "--overwrite" in argv[2:]

    create_db(db_path, overwrite=overwrite)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
