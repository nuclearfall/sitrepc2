CREATE TABLE directions (
    direction_id INTEGER PRIMARY KEY,
    name         TEXT NOT NULL,
    anchor_id    INTEGER NOT NULL,
    anchor_type  TEXT NOT NULL
);
