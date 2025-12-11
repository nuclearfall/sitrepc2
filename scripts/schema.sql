PRAGMA foreign_keys = ON;

----------------------------------------------------------------------
-- 1. Regions  (region_lookup.csv)
--    osm_id,wikidata,iso3166_2,name,aliases,neighbors
----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS regions (
    osm_id      INTEGER PRIMARY KEY,
    wikidata    TEXT,
    iso3166_2   TEXT,
    name        TEXT NOT NULL,
    aliases     TEXT,
    neighbors   TEXT
);

----------------------------------------------------------------------
-- 2. Groups  (group_lookup.csv)
--    name,group_id,aliases,region_ids,neighbor_ids
----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS groups (
    group_id    INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    aliases     TEXT,
    region_ids  TEXT,
    neighbor_ids TEXT
);

----------------------------------------------------------------------
-- 3. Locales  (locale_lookup.csv)
--    name,aliases,place,wikidata,group_id,usage,lon,lat,cid,region_id
--    cid is the primary key, region_id → regions(osm_id)
----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS locales (
    cid        TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    aliases    TEXT,
    place      TEXT,
    wikidata   TEXT,
    group_id   INTEGER,
    usage      TEXT,
    lon        REAL,
    lat        REAL,
    region_id  INTEGER,
    FOREIGN KEY(region_id) REFERENCES regions(osm_id),
    FOREIGN KEY(group_id)  REFERENCES groups(group_id)
);

----------------------------------------------------------------------
-- 4. Aliases
--    Generic alias table (not tied to a CSV above)
--    For locales, use entity_type='locale' and entity_id = locales.cid
----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS aliases (
    entity_type TEXT NOT NULL,
    entity_id   TEXT NOT NULL,
    alias       TEXT NOT NULL,
    normalized  TEXT NOT NULL,
    FOREIGN KEY(entity_id) REFERENCES locales(cid)
);

----------------------------------------------------------------------
-- 5. Directions  (direction_lookup.csv)
--    name,anchor_cid
--    dir_id is an auto-generated key (not present in CSV)
--    anchor_cid → locales.cid
----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS directions (
    dir_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    anchor_cid  TEXT NOT NULL,
    FOREIGN KEY(anchor_cid) REFERENCES locales(cid)
);
