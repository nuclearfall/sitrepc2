PRAGMA foreign_keys = ON;

-- ============================================================
-- ENTITY TABLES
-- ============================================================

-- ------------------------------------------------------------
-- Locations
-- Canonical point locations. Identity is derived from lat/lon.
-- ------------------------------------------------------------
CREATE TABLE locations (
    location_id INTEGER PRIMARY KEY,
    lat          REAL NOT NULL,
    lon          REAL NOT NULL,
    name         TEXT,
    place        TEXT,
    wikidata     TEXT
);

-- ------------------------------------------------------------
-- Regions
-- Administrative regions.
-- region_id values correspond to OSM relation IDs.
-- ------------------------------------------------------------
CREATE TABLE regions (
    region_id   INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    wikidata    TEXT,
    iso3166_2   TEXT
);

-- ------------------------------------------------------------
-- Groups
-- Operational / organizational groupings.
-- ------------------------------------------------------------
CREATE TABLE groups (
    group_id INTEGER PRIMARY KEY,
    name     TEXT NOT NULL
);

-- ------------------------------------------------------------
-- Directions
-- Named operational directions anchored to an entity.
-- anchor_type currently expected: LOCATION or REGION
-- ------------------------------------------------------------
CREATE TABLE directions (
    direction_id INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    anchor_id     INTEGER NOT NULL,
    anchor_type   TEXT NOT NULL
);

-- ============================================================
-- ALIAS TABLES (CANONICAL STORAGE)
-- ============================================================

-- ------------------------------------------------------------
-- Location aliases
-- ------------------------------------------------------------
CREATE TABLE location_aliases (
    location_id INTEGER NOT NULL,
    alias        TEXT NOT NULL,
    normalized   TEXT NOT NULL,
    PRIMARY KEY (location_id, normalized),
    FOREIGN KEY (location_id) REFERENCES locations(location_id)
);

-- ------------------------------------------------------------
-- Region aliases
-- ------------------------------------------------------------
CREATE TABLE region_aliases (
    region_id  INTEGER NOT NULL,
    alias      TEXT NOT NULL,
    normalized TEXT NOT NULL,
    PRIMARY KEY (region_id, normalized),
    FOREIGN KEY (region_id) REFERENCES regions(region_id)
);

-- ------------------------------------------------------------
-- Group aliases
-- ------------------------------------------------------------
CREATE TABLE group_aliases (
    group_id   INTEGER NOT NULL,
    alias      TEXT NOT NULL,
    normalized TEXT NOT NULL,
    PRIMARY KEY (group_id, normalized),
    FOREIGN KEY (group_id) REFERENCES groups(group_id)
);

-- ------------------------------------------------------------
-- Direction aliases
-- ------------------------------------------------------------
CREATE TABLE direction_aliases (
    direction_id INTEGER NOT NULL,
    alias         TEXT NOT NULL,
    normalized    TEXT NOT NULL,
    PRIMARY KEY (direction_id, normalized),
    FOREIGN KEY (direction_id) REFERENCES directions(direction_id)
);

-- ============================================================
-- UNIFIED ALIASES VIEW (FOR LSS / ruler.py ONLY)
-- ============================================================

CREATE VIEW aliases AS
    SELECT 'LOCATION' AS entity_type, location_id AS entity_id, alias, normalized
      FROM location_aliases
    UNION ALL
    SELECT 'REGION', region_id, alias, normalized
      FROM region_aliases
    UNION ALL
    SELECT 'GROUP', group_id, alias, normalized
      FROM group_aliases
    UNION ALL
    SELECT 'DIRECTION', direction_id, alias, normalized
      FROM direction_aliases;

-- ============================================================
-- PIVOT TABLES (DERIVED RELATIONSHIPS)
-- ============================================================

-- ------------------------------------------------------------
-- Location → Region
-- Derived via point-in-polygon.
-- ------------------------------------------------------------
CREATE TABLE location_regions (
    location_id INTEGER NOT NULL,
    region_id   INTEGER NOT NULL,
    PRIMARY KEY (location_id, region_id),
    FOREIGN KEY (location_id) REFERENCES locations(location_id),
    FOREIGN KEY (region_id)   REFERENCES regions(region_id)
);

-- ------------------------------------------------------------
-- Location → Group
-- Derived via AO polygons or operational rules.
-- ------------------------------------------------------------
CREATE TABLE location_groups (
    location_id INTEGER NOT NULL,
    group_id    INTEGER NOT NULL,
    PRIMARY KEY (location_id, group_id),
    FOREIGN KEY (location_id) REFERENCES locations(location_id),
    FOREIGN KEY (group_id)    REFERENCES groups(group_id)
);

-- ------------------------------------------------------------
-- Group → Region
-- Group operational coverage.
-- ------------------------------------------------------------
CREATE TABLE group_regions (
    group_id  INTEGER NOT NULL,
    region_id INTEGER NOT NULL,
    PRIMARY KEY (group_id, region_id),
    FOREIGN KEY (group_id)  REFERENCES groups(group_id),
    FOREIGN KEY (region_id) REFERENCES regions(region_id)
);

-- ------------------------------------------------------------
-- Region ↔ Region adjacency
-- ------------------------------------------------------------
CREATE TABLE region_neighbors (
    region_id          INTEGER NOT NULL,
    neighbor_region_id INTEGER NOT NULL,
    PRIMARY KEY (region_id, neighbor_region_id),
    FOREIGN KEY (region_id)          REFERENCES regions(region_id),
    FOREIGN KEY (neighbor_region_id) REFERENCES regions(region_id)
);

-- ------------------------------------------------------------
-- Group ↔ Group adjacency
-- ------------------------------------------------------------
CREATE TABLE group_neighbors (
    group_id          INTEGER NOT NULL,
    neighbor_group_id INTEGER NOT NULL,
    PRIMARY KEY (group_id, neighbor_group_id),
    FOREIGN KEY (group_id)          REFERENCES groups(group_id),
    FOREIGN KEY (neighbor_group_id) REFERENCES groups(group_id)
);
