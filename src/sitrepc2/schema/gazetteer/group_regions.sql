CREATE TABLE group_regions (
    group_id  INTEGER NOT NULL,
    region_id INTEGER NOT NULL,
    PRIMARY KEY (group_id, region_id),
    FOREIGN KEY (group_id)  REFERENCES groups(group_id),
    FOREIGN KEY (region_id) REFERENCES regions(region_id)
);
