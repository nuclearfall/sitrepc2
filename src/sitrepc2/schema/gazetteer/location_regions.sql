CREATE TABLE location_regions (
    location_id INTEGER NOT NULL,
    region_id   INTEGER NOT NULL,
    PRIMARY KEY (location_id, region_id),
    FOREIGN KEY (location_id) REFERENCES locations(location_id),
    FOREIGN KEY (region_id)   REFERENCES regions(region_id)
);
