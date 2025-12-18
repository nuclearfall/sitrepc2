CREATE TABLE region_aliases (
    region_id  INTEGER NOT NULL,
    alias      TEXT NOT NULL,
    normalized TEXT NOT NULL,
    PRIMARY KEY (region_id, normalized),
    FOREIGN KEY (region_id) REFERENCES regions(region_id)
);
