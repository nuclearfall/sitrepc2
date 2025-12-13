PRAGMA foreign_keys = ON;

----------------------------------------------------------------------
-- POSTS
----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS posts (
    post_id         TEXT PRIMARY KEY,
    source          TEXT NOT NULL,
    channel         TEXT NOT NULL,
    channel_lang    TEXT,
    published_at    TEXT NOT NULL,
    fetched_at      TEXT NOT NULL,
    text            TEXT NOT NULL,
    enabled         BOOLEAN NOT NULL DEFAULT 1
);

----------------------------------------------------------------------
-- SECTIONS
----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS sections (
    section_id      TEXT PRIMARY KEY,
    post_id         TEXT NOT NULL,
    position        INTEGER NOT NULL,
    text            TEXT NOT NULL,
    enabled         BOOLEAN NOT NULL DEFAULT 1,

    FOREIGN KEY (post_id) REFERENCES posts(post_id)
        ON DELETE CASCADE
);

----------------------------------------------------------------------
-- EVENT CLAIMS
----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS event_claims (
    claim_id        TEXT PRIMARY KEY,
    post_id         TEXT NOT NULL,
    section_id      TEXT NOT NULL,
    text            TEXT NOT NULL,
    negated         BOOLEAN NOT NULL DEFAULT 0,
    uncertain       BOOLEAN NOT NULL DEFAULT 0,
    enabled         BOOLEAN NOT NULL DEFAULT 1,

    FOREIGN KEY (post_id) REFERENCES posts(post_id)
        ON DELETE CASCADE,
    FOREIGN KEY (section_id) REFERENCES sections(section_id)
        ON DELETE CASCADE
);

----------------------------------------------------------------------
-- LOCATION HINTS (unresolved locations)
----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS location_hints (
    location_id         TEXT PRIMARY KEY,
    claim_id            TEXT NOT NULL,
    text                TEXT NOT NULL,
    asserted            BOOLEAN NOT NULL,
    source              TEXT NOT NULL,
    enabled             BOOLEAN NOT NULL DEFAULT 1,

    FOREIGN KEY (claim_id) REFERENCES event_claims(claim_id)
        ON DELETE CASCADE
);

----------------------------------------------------------------------
-- CONTEXT HINTS (scoped semantics)
----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS context_hints (
    context_id      TEXT PRIMARY KEY,

    kind            TEXT NOT NULL,   -- REGION | GROUP | DIRECTION | PROXIMITY
    text            TEXT NOT NULL,

    scope           TEXT NOT NULL,   -- POST | SECTION | CLAIM | LOCATION
    source          TEXT NOT NULL,   -- lss | user

    post_id         TEXT,
    section_id      TEXT,
    claim_id        TEXT,
    location_id     TEXT,

    enabled         BOOLEAN NOT NULL DEFAULT 1,

    FOREIGN KEY (post_id) REFERENCES posts(post_id)
        ON DELETE CASCADE,
    FOREIGN KEY (section_id) REFERENCES sections(section_id)
        ON DELETE CASCADE,
    FOREIGN KEY (claim_id) REFERENCES event_claims(claim_id)
        ON DELETE CASCADE,
    FOREIGN KEY (location_id) REFERENCES location_hints(location_id)
        ON DELETE CASCADE
);

----------------------------------------------------------------------
-- ACTOR HINTS
----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS actor_hints (
    actor_hint_id   TEXT PRIMARY KEY,
    claim_id        TEXT NOT NULL,
    text            TEXT NOT NULL,
    kind_hint       TEXT NOT NULL,
    source          TEXT NOT NULL,
    enabled         BOOLEAN NOT NULL DEFAULT 1,

    FOREIGN KEY (claim_id) REFERENCES event_claims(claim_id)
        ON DELETE CASCADE
);

----------------------------------------------------------------------
-- ACTION HINTS
----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS action_hints (
    action_hint_id  TEXT PRIMARY KEY,
    claim_id        TEXT NOT NULL,
    text            TEXT NOT NULL,
    source          TEXT NOT NULL,
    enabled         BOOLEAN NOT NULL DEFAULT 1,

    FOREIGN KEY (claim_id) REFERENCES event_claims(claim_id)
        ON DELETE CASCADE
);
