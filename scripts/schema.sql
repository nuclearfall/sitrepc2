-- Locales: CID is now the primary key
CREATE TABLE IF NOT EXISTS locales (
    cid TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    place TEXT,
    wikidata TEXT,
    group_id INTEGER,
    lon REAL,
    lat REAL,
    region_osm_id INTEGER
);

-- Aliases: FK references CID
CREATE TABLE IF NOT EXISTS aliases (
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,       -- stores CID for locales
    alias TEXT NOT NULL,
    normalized TEXT NOT NULL,
    FOREIGN KEY(entity_id) REFERENCES locales(cid)
);

-- Regions
CREATE TABLE IF NOT EXISTS regions (
    osm_id INTEGER PRIMARY KEY,
    wikidata TEXT,
    iso3166_2 TEXT,
    name TEXT NOT NULL,
    aliases TEXT,
    neighbors TEXT
);

-- Groups
CREATE TABLE IF NOT EXISTS groups (
    group_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    aliases TEXT,
    neighbor_groups TEXT,
    regions TEXT
);

-- Directions
CREATE TABLE IF NOT EXISTS directions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    direction TEXT NOT NULL,
    cid TEXT NOT NULL,
    FOREIGN KEY(cid) REFERENCES locales(cid)
);

