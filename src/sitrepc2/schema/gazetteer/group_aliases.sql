CREATE TABLE group_aliases (
    group_id   INTEGER NOT NULL,
    alias      TEXT NOT NULL,
    normalized TEXT NOT NULL,
    PRIMARY KEY (group_id, normalized),
    FOREIGN KEY (group_id) REFERENCES groups(group_id)
);
