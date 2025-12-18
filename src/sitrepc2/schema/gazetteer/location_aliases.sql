CREATE TABLE location_aliases (
    location_id INTEGER NOT NULL,
    alias        TEXT NOT NULL,
    normalized   TEXT NOT NULL,
    PRIMARY KEY (location_id, normalized),
    FOREIGN KEY (location_id) REFERENCES locations(location_id)
);
