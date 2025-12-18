CREATE TABLE direction_aliases (
    direction_id INTEGER NOT NULL,
    alias         TEXT NOT NULL,
    normalized    TEXT NOT NULL,
    PRIMARY KEY (direction_id, normalized),
    FOREIGN KEY (direction_id) REFERENCES directions(direction_id)
);
