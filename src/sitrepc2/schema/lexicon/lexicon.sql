PRAGMA foreign_keys = ON;

CREATE TABLE event_phrases (
    label TEXT PRIMARY KEY,
    phrase TEXT NOT NULL
);

CREATE TABLE context_phrases (
    label TEXT PRIMARY KEY,
    phrase TEXT NOT NULL
);
