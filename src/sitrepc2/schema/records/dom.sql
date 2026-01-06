PRAGMA foreign_keys = ON;

----------------------------------------------------------------------
-- DOM (Domain Object Model) Persistence Schema
--
-- Properties:
-- • Append-only snapshots
-- • Immutable structure & provenance
-- • Snapshot-scoped review state
-- • No token spans persisted
-- • Single linear lifecycle per post
----------------------------------------------------------------------

----------------------------------------------------------------------
-- 1. Lifecycle Stages
----------------------------------------------------------------------

CREATE TABLE dom_lifecycle_stage (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

/*
1 = CREATED
2 = INITIAL_REVIEW
3 = PROCESSED
4 = FINAL_REVIEW
5 = AUDIT
*/

----------------------------------------------------------------------
-- 2. DOM Post Anchor
----------------------------------------------------------------------

CREATE TABLE dom_post (
    id INTEGER PRIMARY KEY,
    ingest_post_id INTEGER NOT NULL,
    lss_run_id INTEGER NOT NULL,

    UNIQUE (ingest_post_id, lss_run_id)
);

----------------------------------------------------------------------
-- 3. DOM Snapshot (Append-Only, Linear Lifecycle)
----------------------------------------------------------------------

CREATE TABLE dom_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dom_post_id INTEGER NOT NULL,
    lifecycle_stage_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,

    FOREIGN KEY (dom_post_id)
        REFERENCES dom_post(id)
        ON DELETE CASCADE,

    FOREIGN KEY (lifecycle_stage_id)
        REFERENCES dom_lifecycle_stage(id),

    UNIQUE (dom_post_id, lifecycle_stage_id)
);

----------------------------------------------------------------------
-- 4. DOM Node Structure (Immutable)
----------------------------------------------------------------------

CREATE TABLE dom_node (
    id INTEGER PRIMARY KEY,
    dom_post_id INTEGER NOT NULL,

    node_type TEXT NOT NULL CHECK (
        node_type IN (
            'POST',
            'SECTION',
            'EVENT',
            'LOCATION_SERIES',
            'LOCATION',
            'LOCATION_CANDIDATE'
        )
    ),

    parent_id INTEGER,
    sibling_order INTEGER NOT NULL,

    FOREIGN KEY (dom_post_id)
        REFERENCES dom_post(id)
        ON DELETE CASCADE,

    FOREIGN KEY (parent_id)
        REFERENCES dom_node(id)
        ON DELETE CASCADE
);

----------------------------------------------------------------------
-- 5. DOM Node Provenance (Immutable, Token-Free)
----------------------------------------------------------------------

CREATE TABLE dom_node_provenance (
    dom_node_id INTEGER PRIMARY KEY,

    lss_event_id INTEGER,
    lss_section_ids TEXT,        -- JSON array of contributing section IDs
    gazetteer_entity_id INTEGER,

    FOREIGN KEY (dom_node_id)
        REFERENCES dom_node(id)
        ON DELETE CASCADE
);

----------------------------------------------------------------------
-- 6. Snapshot-Scoped Node State (Review + Derived)
----------------------------------------------------------------------

CREATE TABLE dom_node_state (
    dom_snapshot_id INTEGER NOT NULL,
    dom_node_id INTEGER NOT NULL,

    selected BOOLEAN NOT NULL,
    summary TEXT NOT NULL,

    resolved BOOLEAN,                  -- LOCATION / LOCATION_CANDIDATE only
    resolution_source TEXT CHECK (
        resolution_source IN ('AUTO', 'MANUAL')
    ),

    -- Dedupe state (CORE FIELD — NOT A MIGRATION)
    deduped BOOLEAN NOT NULL DEFAULT FALSE,
    dedupe_target_id INTEGER,

    PRIMARY KEY (dom_snapshot_id, dom_node_id),

    FOREIGN KEY (dom_snapshot_id)
        REFERENCES dom_snapshot(id)
        ON DELETE CASCADE,

    FOREIGN KEY (dom_node_id)
        REFERENCES dom_node(id)
        ON DELETE CASCADE,

    FOREIGN KEY (dedupe_target_id)
        REFERENCES dom_node(id)
);

----------------------------------------------------------------------
-- 7. Context Metadata (Snapshot-Scoped, Override-Aware)
----------------------------------------------------------------------

CREATE TABLE dom_context (
    dom_snapshot_id INTEGER NOT NULL,
    dom_node_id INTEGER NOT NULL,

    ctx_kind TEXT NOT NULL CHECK (
        ctx_kind IN ('REGION', 'GROUP', 'DIRECTION')
    ),
    ctx_value TEXT NOT NULL,

    overridden BOOLEAN NOT NULL,

    FOREIGN KEY (dom_snapshot_id)
        REFERENCES dom_snapshot(id)
        ON DELETE CASCADE,

    FOREIGN KEY (dom_node_id)
        REFERENCES dom_node(id)
        ON DELETE CASCADE
);

CREATE INDEX idx_dom_context_snapshot
    ON dom_context(dom_snapshot_id);

CREATE INDEX idx_dom_context_node
    ON dom_context(dom_node_id);

----------------------------------------------------------------------
-- 8. Actors (Metadata, Event-Scoped)
----------------------------------------------------------------------

CREATE TABLE dom_actor (
    dom_snapshot_id INTEGER NOT NULL,
    event_node_id INTEGER NOT NULL,

    actor_text TEXT NOT NULL,
    gazetteer_group_id INTEGER,
    selected BOOLEAN NOT NULL,

    FOREIGN KEY (dom_snapshot_id)
        REFERENCES dom_snapshot(id)
        ON DELETE CASCADE,

    FOREIGN KEY (event_node_id)
        REFERENCES dom_node(id)
        ON DELETE CASCADE
);

----------------------------------------------------------------------
-- 9. Location Candidates (Snapshot-Scoped)
----------------------------------------------------------------------

CREATE TABLE dom_location_candidate (
    dom_snapshot_id INTEGER NOT NULL,
    location_node_id INTEGER NOT NULL,

    -- Provenance
    gazetteer_location_id INTEGER,

    -- Embedded snapshot of gazetteer.locations
    lat REAL,
    lon REAL,
    name TEXT,
    place TEXT,
    wikidata TEXT,

    -- Review metadata
    confidence REAL,
    dist_from_front REAL,
    selected BOOLEAN NOT NULL,
    persists BOOLEAN NOT NULL,     -- session-only vs patch-eligible

    FOREIGN KEY (dom_snapshot_id)
        REFERENCES dom_snapshot(id)
        ON DELETE CASCADE,

    FOREIGN KEY (location_node_id)
        REFERENCES dom_node(id)
        ON DELETE CASCADE
);

----------------------------------------------------------------------
-- 10. Commit Eligibility (Derived, Snapshot-Scoped)
----------------------------------------------------------------------

CREATE TABLE dom_commit_eligibility (
    dom_snapshot_id INTEGER NOT NULL,
    dom_node_id INTEGER NOT NULL,

    eligible BOOLEAN NOT NULL,
    reason TEXT,                   -- e.g. 'UNRESOLVED', 'DESELECTED'

    PRIMARY KEY (dom_snapshot_id, dom_node_id),

    FOREIGN KEY (dom_snapshot_id)
        REFERENCES dom_snapshot(id)
        ON DELETE CASCADE,

    FOREIGN KEY (dom_node_id)
        REFERENCES dom_node(id)
        ON DELETE CASCADE
);
