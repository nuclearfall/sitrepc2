PRAGMA foreign_keys = ON;

----------------------------------------------------------------------
-- LSS (Lexical–Structural–Semantic) layer schema
--
-- This schema defines ALL outputs produced by the LSS layer.
-- LSS consumes ingest_posts and produces:
--   - execution metadata (runs)
--   - optional section groupings
--   - structurally extracted events
--   - role candidates anchored to event text
--   - optional contextual spans
--
-- LSS performs NO domain resolution.
-- All records are text-anchored and provenance-preserving.
-- lss_* tables are WRITE-ONCE.
-- Downstream layers must not UPDATE or DELETE rows.

----------------------------------------------------------------------

----------------------------------------------------------------------
-- LSS runs
-- One row per execution of LSS over a single ingest_post
----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS lss_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    ingest_post_id INTEGER NOT NULL,

    started_at TEXT NOT NULL,              -- UTC ISO-8601
    completed_at TEXT,                     -- UTC ISO-8601

    engine TEXT NOT NULL,                  -- e.g. 'holmes'
    engine_version TEXT,
    model TEXT,

    FOREIGN KEY (ingest_post_id)
        REFERENCES ingest_posts(id)
        ON DELETE CASCADE
);

----------------------------------------------------------------------
-- LSS sections (optional grouping context)
-- Sections exist only if LSS detects shared context across events
----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS lss_sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    lss_run_id INTEGER NOT NULL,
    ingest_post_id INTEGER NOT NULL,

    -- Text anchoring
    text TEXT NOT NULL,
    start_token INTEGER,
    end_token INTEGER,

    -- Ordering within the post
    ordinal INTEGER NOT NULL,

    FOREIGN KEY (lss_run_id)
        REFERENCES lss_runs(id)
        ON DELETE CASCADE,

    FOREIGN KEY (ingest_post_id)
        REFERENCES ingest_posts(id)
        ON DELETE CASCADE
);

----------------------------------------------------------------------
-- LSS events (core structural output)
----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS lss_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    lss_run_id INTEGER NOT NULL,
    ingest_post_id INTEGER NOT NULL,
    section_id INTEGER,

    -- Holmes identity
    event_uid TEXT NOT NULL,               -- EventMatch.event_id
    label TEXT NOT NULL,                   -- Holmes rule / label
    search_phrase TEXT NOT NULL,

    -- Text anchoring
    text TEXT NOT NULL,                    -- sentences_within_document
    start_token INTEGER NOT NULL,
    end_token INTEGER NOT NULL,

    -- Structural confidence & flags
    similarity REAL,
    negated BOOLEAN NOT NULL,
    uncertain BOOLEAN NOT NULL,
    involves_coreference BOOLEAN NOT NULL,

    -- Ordering within section or post
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
-- Derived from WordMatch; no resolution is performed here
----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS lss_role_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    lss_event_id INTEGER NOT NULL,

    -- Inferred role kind (derived, not resolved)
    role_kind TEXT NOT NULL,               -- ACTOR / ACTION / LOCATION

    -- Matched text
    document_word TEXT NOT NULL,
    document_phrase TEXT,

    -- Text anchoring
    start_token INTEGER NOT NULL,
    end_token INTEGER NOT NULL,

    -- LSS signals
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
-- LSS context spans (optional)
-- Contextual entities not yet bound to a specific event
----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS lss_context_spans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    lss_run_id INTEGER NOT NULL,
    ingest_post_id INTEGER NOT NULL,

    ctx_kind TEXT NOT NULL,                -- LOCATION / REGION / GROUP / DIRECTION
    text TEXT NOT NULL,

    start_token INTEGER,
    end_token INTEGER,

    FOREIGN KEY (lss_run_id)
        REFERENCES lss_runs(id)
        ON DELETE CASCADE,

    FOREIGN KEY (ingest_post_id)
        REFERENCES ingest_posts(id)
        ON DELETE CASCADE
);

----------------------------------------------------------------------
-- Indexes for efficient downstream consumption (DOM / review / audit)
-- These indexes do NOT change semantics.
----------------------------------------------------------------------

-- -------------------------------------------------
-- LSS runs
-- -------------------------------------------------

-- Lookup latest / completed runs per ingest post
CREATE INDEX IF NOT EXISTS idx_lss_runs_ingest_post
ON lss_runs(ingest_post_id);

CREATE INDEX IF NOT EXISTS idx_lss_runs_completed
ON lss_runs(completed_at);


-- -------------------------------------------------
-- LSS sections
-- -------------------------------------------------

-- Fetch sections for a run in order
CREATE INDEX IF NOT EXISTS idx_lss_sections_run
ON lss_sections(lss_run_id, ordinal);

-- Optional: direct lookup by ingest post
CREATE INDEX IF NOT EXISTS idx_lss_sections_ingest_post
ON lss_sections(ingest_post_id);


-- -------------------------------------------------
-- LSS events
-- -------------------------------------------------

-- Primary DOM entry point: all events for a run
CREATE INDEX IF NOT EXISTS idx_lss_events_run
ON lss_events(lss_run_id);

-- Section-scoped event ordering
CREATE INDEX IF NOT EXISTS idx_lss_events_section
ON lss_events(section_id, ordinal);

-- Event lookup by ingest post (audit, replay)
CREATE INDEX IF NOT EXISTS idx_lss_events_ingest_post
ON lss_events(ingest_post_id);


-- -------------------------------------------------
-- LSS role candidates
-- -------------------------------------------------

-- Primary join: role candidates → events
CREATE INDEX IF NOT EXISTS idx_lss_role_candidates_event
ON lss_role_candidates(lss_event_id);

-- Role-kind filtering (ACTOR / ACTION / LOCATION)
CREATE INDEX IF NOT EXISTS idx_lss_role_candidates_kind
ON lss_role_candidates(role_kind);


-- -------------------------------------------------
-- LSS context spans
-- -------------------------------------------------

-- Fetch all contexts for a run
CREATE INDEX IF NOT EXISTS idx_lss_context_spans_run
ON lss_context_spans(lss_run_id);

-- Context lookup by ingest post (review UI)
CREATE INDEX IF NOT EXISTS idx_lss_context_spans_ingest_post
ON lss_context_spans(ingest_post_id);

-- Context kind filtering (REGION / GROUP / DIRECTION / PROXIMITY)
CREATE INDEX IF NOT EXISTS idx_lss_context_spans_kind
ON lss_context_spans(ctx_kind);
