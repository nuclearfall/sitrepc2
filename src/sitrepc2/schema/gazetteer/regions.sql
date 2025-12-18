CREATE TABLE regions (
    region_id   INTEGER PRIMARY KEY,   -- OSM relation ID
    name        TEXT NOT NULL,
    wikidata    TEXT,
    iso3166_2   TEXT
);
