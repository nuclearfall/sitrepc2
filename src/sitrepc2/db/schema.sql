PRAGMA foreign_keys = ON;

----------------------------------------------------------------------
-- 1. Metadata table
--    Stores pipeline version, last processed times, etc.
----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

----------------------------------------------------------------------
-- 2. Telegram Posts (Deduped by post_id)
----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS posts (
    post_id        INTEGER PRIMARY KEY,   -- Telegram message.id
    channel        TEXT NOT NULL,
    alias          TEXT NOT NULL,
    published_at   TEXT NOT NULL,         -- ISO UTC
    fetched_at     TEXT NOT NULL,         -- ISO UTC
    lang           TEXT NOT NULL,
    raw_json       TEXT                   -- Serialized message object
);

-- Index to speed lookups by channel/date
CREATE INDEX IF NOT EXISTS idx_posts_channel_date
    ON posts(channel, published_at);

----------------------------------------------------------------------
-- 3. Post Text (Raw or Translated)
--    One-to-one with posts
----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS post_text (
    post_id      INTEGER PRIMARY KEY REFERENCES posts(post_id) ON DELETE CASCADE,
    raw_text     TEXT,                    -- original text
    clean_text   TEXT,                    -- normalized text for NLP
    translated   INTEGER DEFAULT 0 CHECK (translated IN (0,1))
);

----------------------------------------------------------------------
-- 4. Raw Event Matches (Holmes/LSS Layer)
--    Deduplication via hash ensures each EventMatch is stored once.
----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS events_raw (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id      INTEGER NOT NULL REFERENCES posts(post_id) ON DELETE CASCADE,
    event_json   TEXT NOT NULL,
    hash         TEXT NOT NULL UNIQUE      -- hash(EventMatch) for dedupe
);

CREATE INDEX IF NOT EXISTS idx_events_raw_post_id
    ON events_raw(post_id);

----------------------------------------------------------------------
-- 5. Domain Events (Interpreted DOM Layer)
--    Multiple DOM events may come from the same raw event.
----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS events_dom (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_event_id  INTEGER NOT NULL REFERENCES events_raw(id) ON DELETE CASCADE,
    dom_json      TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending','audited','final'))
);

CREATE INDEX IF NOT EXISTS idx_events_dom_status
    ON events_dom(status);

----------------------------------------------------------------------
-- 6. Location Candidates (Ambiguity Tracking)
--    Each DOM event may produce 0..N candidate locations.
----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS locations (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    event_dom_id   INTEGER NOT NULL REFERENCES events_dom(id) ON DELETE CASCADE,
    name           TEXT NOT NULL,            -- matched name
    qid            TEXT,                     -- wikidata QID
    osm_id         TEXT,                     -- OSM node/way/relation
    anchor_dir     TEXT,                     -- kupiansk, liman, etc.
    confidence     REAL,                     -- numeric confidence score
    resolved       INTEGER DEFAULT 0 CHECK (resolved IN (0,1))
);

CREATE INDEX IF NOT EXISTS idx_locations_event
    ON locations(event_dom_id);

----------------------------------------------------------------------
-- 7. Audit requirements
--    Tracks unresolved issues requiring analyst intervention.
----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_requirements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_dom_id    INTEGER NOT NULL REFERENCES events_dom(id) ON DELETE CASCADE,
    issue_type      TEXT NOT NULL,     -- ambiguous_location, missing_anchor, etc.
    issue_json      TEXT NOT NULL,     -- payload for UI rendering
    resolved        INTEGER DEFAULT 0 CHECK (resolved IN (0,1))
);

CREATE INDEX IF NOT EXISTS idx_audit_event
    ON audit_requirements(event_dom_id);

----------------------------------------------------------------------
-- 8. Final, Reviewed Events (User-approved)
--    These events are the authoritative results of the pipeline.
----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS final_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    event_dom_id  INTEGER UNIQUE NOT NULL REFERENCES events_dom(id) ON DELETE CASCADE,
    final_json    TEXT NOT NULL,
    committed_at  TEXT NOT NULL         -- ISO UTC timestamp
);

CREATE INDEX IF NOT EXISTS idx_final_committed
    ON final_events(committed_at);

----------------------------------------------------------------------
-- 9. Optional staging table for user UI state
----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ui_state (
    key TEXT PRIMARY KEY,
    value TEXT
);
