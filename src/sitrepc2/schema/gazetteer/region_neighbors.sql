CREATE TABLE region_neighbors (
    region_id          INTEGER NOT NULL,
    neighbor_region_id INTEGER NOT NULL,
    PRIMARY KEY (region_id, neighbor_region_id),
    FOREIGN KEY (region_id)          REFERENCES regions(region_id),
    FOREIGN KEY (neighbor_region_id) REFERENCES regions(region_id)
);
