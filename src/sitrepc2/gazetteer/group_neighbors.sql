CREATE TABLE group_neighbors (
    group_id          INTEGER NOT NULL,
    neighbor_group_id INTEGER NOT NULL,
    PRIMARY KEY (group_id, neighbor_group_id),
    FOREIGN KEY (group_id)          REFERENCES groups(group_id),
    FOREIGN KEY (neighbor_group_id) REFERENCES groups(group_id)
);
