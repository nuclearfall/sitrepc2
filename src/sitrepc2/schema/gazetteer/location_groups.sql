CREATE TABLE location_groups (
    location_id INTEGER NOT NULL,
    group_id    INTEGER NOT NULL,
    PRIMARY KEY (location_id, group_id),
    FOREIGN KEY (location_id) REFERENCES locations(location_id),
    FOREIGN KEY (group_id)    REFERENCES groups(group_id)
);
