PRAGMA foreign_keys = ON;

----------------------------------------------------------------------
-- LSS (Lexical–Structural–Semantic) layer schema
--
-- LSS performs STRUCTURAL extraction only.
-- No resolution, no disambiguation, no inference beyond spans.
-- All rows are text-anchored and provenance-preserving.
-- All lss_* tables are append-only.
----------------------------------------------------------------------

----------------------------------------------------------------------
-- LSS runs
----------------------------------------------------------------------

CREATE TABLE lss_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ingest_post_id INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    engine TEXT NOT NULL,
    engine_version TEXT,
    model TEXT,
    FOREIGN KEY (ingest_post_id)
        REFERENCES ingest_posts(id)
        ON DELETE CASCADE
);

----------------------------------------------------------------------
-- LSS sections (optional structural grouping)
----------------------------------------------------------------------

CREATE TABLE lss_sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lss_run_id INTEGER NOT NULL,
    ingest_post_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    start_token INTEGER,
    end_token INTEGER,
    ordinal INTEGER NOT NULL,
    FOREIGN KEY (lss_run_id)
        REFERENCES lss_runs(id)
        ON DELETE CASCADE,
    FOREIGN KEY (ingest_post_id)
        REFERENCES ingest_posts(id)
        ON DELETE CASCADE
);

----------------------------------------------------------------------
-- LSS events
-- Events have NO direct spatial references.
-- Spatial anchoring is provided exclusively via LocationSeries.
----------------------------------------------------------------------

CREATE TABLE lss_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lss_run_id INTEGER NOT NULL,
    ingest_post_id INTEGER NOT NULL,
    section_id INTEGER,
    event_uid TEXT NOT NULL,
    label TEXT NOT NULL,
    search_phrase TEXT NOT NULL,
    text TEXT NOT NULL,
    start_token INTEGER NOT NULL,
    end_token INTEGER NOT NULL,
    similarity REAL,
    negated BOOLEAN NOT NULL,
    uncertain BOOLEAN NOT NULL,
    involves_coreference BOOLEAN NOT NULL,
    ordinal INTEGER NOT NULL,
    FOREIGN KEY (lss_run_id)
        REFERENCES lss_runs(id)
        ON DELETE CASCADE,
    FOREIGN KEY (ingest_post_id)
        REFERENCES ingest_posts(id)
        ON DELETE CASCADE,
    FOREIGN KEY (section_id)
        REFERENCES lss_sections(id)
        ON DELETE SET NULL
);

----------------------------------------------------------------------
-- LSS role candidates
-- Semantic roles only (Holmes-derived)
-- LOCATION IS EXPLICITLY NOT A ROLE
----------------------------------------------------------------------

CREATE TABLE lss_role_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lss_event_id INTEGER NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('HOLMES')),
    role_kind TEXT NOT NULL CHECK (role_kind IN ('ACTOR','ACTION')),
    text TEXT NOT NULL,
    start_token INTEGER NOT NULL,
    end_token INTEGER NOT NULL,
    match_type TEXT,
    negated BOOLEAN NOT NULL,
    uncertain BOOLEAN NOT NULL,
    involves_coreference BOOLEAN NOT NULL,
    similarity REAL,
    explanation TEXT,
    FOREIGN KEY (lss_event_id)
        REFERENCES lss_events(id)
        ON DELETE CASCADE
);

----------------------------------------------------------------------
-- LSS location series
-- Every event must have >= 1 series (enforced in code)
----------------------------------------------------------------------

CREATE TABLE lss_location_series (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lss_event_id INTEGER NOT NULL,
    start_token INTEGER NOT NULL,
    end_token INTEGER NOT NULL,
    FOREIGN KEY (lss_event_id)
        REFERENCES lss_events(id)
        ON DELETE CASCADE
);

----------------------------------------------------------------------
-- LSS location items (members of a series)
----------------------------------------------------------------------

CREATE TABLE lss_location_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    series_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    start_token INTEGER NOT NULL,
    end_token INTEGER NOT NULL,
    ordinal INTEGER NOT NULL,
    FOREIGN KEY (series_id)
        REFERENCES lss_location_series(id)
        ON DELETE CASCADE
);

----------------------------------------------------------------------
-- LSS context hints
-- Unified contextualization across all structural levels
----------------------------------------------------------------------

CREATE TABLE lss_context_hints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lss_run_id INTEGER NOT NULL,
    ctx_kind TEXT NOT NULL
        CHECK (ctx_kind IN ('REGION','GROUP','DIRECTION')),
    text TEXT NOT NULL,
    start_token INTEGER NOT NULL,
    end_token INTEGER NOT NULL,
    scope TEXT NOT NULL
        CHECK (scope IN ('LOCATION','SERIES','EVENT','SECTION','POST')),
    target_id INTEGER,
    source TEXT NOT NULL CHECK (source IN ('GAZETTEER')),
    FOREIGN KEY (lss_run_id)
        REFERENCES lss_runs(id)
        ON DELETE CASCADE
);

----------------------------------------------------------------------
-- Indexes (performance only; no semantic meaning)
----------------------------------------------------------------------

CREATE INDEX idx_lss_runs_ingest_post
    ON lss_runs(ingest_post_id);

CREATE INDEX idx_lss_sections_run
    ON lss_sections(lss_run_id, ordinal);

CREATE INDEX idx_lss_events_run
    ON lss_events(lss_run_id);

CREATE INDEX idx_lss_events_section
    ON lss_events(section_id, ordinal);

CREATE INDEX idx_lss_role_candidates_event
    ON lss_role_candidates(lss_event_id);

CREATE INDEX idx_lss_location_series_event
    ON lss_location_series(lss_event_id);

CREATE INDEX idx_lss_location_items_series
    ON lss_location_items(series_id, ordinal);

CREATE INDEX idx_lss_context_hints_run
    ON lss_context_hints(lss_run_id);

CREATE INDEX idx_lss_context_hints_scope
    ON lss_context_hints(scope, ctx_kind);
