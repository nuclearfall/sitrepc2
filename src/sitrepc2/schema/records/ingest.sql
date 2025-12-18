PRAGMA foreign_keys = ON;

----------------------------------------------------------------------
-- Ingest: generic source posts
-- This table is written by ALL ingest adapters (telegram, x, web, rss)
----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ingest_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Source identity
    source TEXT NOT NULL,                 -- e.g. 'telegram', 'x', 'web', 'rss'
    publisher TEXT NOT NULL,              -- channel / account / site
    source_post_id TEXT NOT NULL,          -- upstream ID (msg id, tweet id, URL, GUID)

    -- Human-facing metadata
    alias TEXT NOT NULL,                  -- display label (e.g. 'Rybar')
    lang TEXT NOT NULL,                   -- ISO-ish language code

    -- Temporal metadata
    published_at TEXT NOT NULL,            -- UTC ISO-8601
    fetched_at TEXT NOT NULL,              -- UTC ISO-8601

    -- Canonical content
    text TEXT NOT NULL,

    -- Idempotency / dedupe
    UNIQUE (source, publisher, source_post_id)
);

----------------------------------------------------------------------
-- (Future tables will live alongside this)
-- nlp_runs, nlp_extractions, dom_events, etc.
----------------------------------------------------------------------
