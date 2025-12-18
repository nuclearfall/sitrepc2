CREATE TABLE locations (
    location_id INTEGER PRIMARY KEY,
    lat         REAL NOT NULL,
    lon         REAL NOT NULL,
    name        TEXT,
    place       TEXT,
    wikidata    TEXT
);
