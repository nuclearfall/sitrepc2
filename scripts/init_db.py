# scripts/init_db.py
from __future__ import annotations

import sqlite3
from pathlib import Path

from sitrepc2.config.paths import current_dotpath
from .import_region_lookup import import_regions
from .import_group_lookup import import_groups
from .import_locale_lookup import import_locales
from .import_direction_lookup import import_directions


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

----------------------------------------------------------------------
-- 1. Regions  (region_lookup.csv)
--    osm_id,wikidata,iso3166_2,name,aliases,neighbors
----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS regions (
    osm_id      INTEGER PRIMARY KEY,
    wikidata    TEXT,
    iso3166_2   TEXT,
    name        TEXT NOT NULL,
    aliases     TEXT,
    neighbors   TEXT
);

----------------------------------------------------------------------
-- 2. Groups  (group_lookup.csv)
--    name,group_id,aliases,region_ids,neighbor_ids
----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS groups (
    group_id     INTEGER PRIMARY KEY,
    name         TEXT NOT NULL,
    aliases      TEXT,
    region_ids   TEXT,
    neighbor_ids TEXT
);

----------------------------------------------------------------------
-- 3. Locales  (locale_lookup.csv)
--    name,aliases,place,wikidata,group_id,usage,lon,lat,cid,region_id
--    cid is the primary key, region_id → regions(osm_id)
----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS locales (
    cid        TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    aliases    TEXT,
    place      TEXT,
    wikidata   TEXT,
    group_id   INTEGER,
    usage      TEXT,
    lon        REAL,
    lat        REAL,
    region_id  INTEGER,
    FOREIGN KEY(region_id) REFERENCES regions(osm_id),
    FOREIGN KEY(group_id)  REFERENCES groups(group_id)
);

----------------------------------------------------------------------
-- 4. Aliases
--    Generic alias table (not tied to a CSV above)
--    For locales, use entity_type='locale' and entity_id = locales.cid
----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS aliases (
    entity_type TEXT NOT NULL,
    entity_id   TEXT NOT NULL,
    alias       TEXT NOT NULL,
    normalized  TEXT NOT NULL,
    FOREIGN KEY(entity_id) REFERENCES locales(cid)
);

----------------------------------------------------------------------
-- 5. Directions  (direction_lookup.csv)
--    name,anchor_cid
--    dir_id is an auto-generated key (not present in CSV)
--    anchor_cid → locales.cid
----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS directions (
    dir_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    anchor_cid  TEXT NOT NULL,
    FOREIGN KEY(anchor_cid) REFERENCES locales(cid)
);
"""


def run() -> None:
    """
    Initialize the sitrepc2 SQLite database:

      1. Create (or update) schema.
      2. Import CSV-backed lookup tables in FK-safe order.

    Resulting DB path: <current_dotpath()>/sitrepc2.db
    """
    dot = current_dotpath()
    dot.mkdir(parents=True, exist_ok=True)

    db_path = dot / "sitrepc2.db"
    print(f"📂 Using database at: {db_path}")

    conn = sqlite3.connect(db_path)
    try:
        # Ensure foreign keys are enforced for this connection
        conn.execute("PRAGMA foreign_keys = ON;")

        print("🛠  Applying schema ...")
        conn.executescript(SCHEMA_SQL)
        print("✔ Schema applied.")

        # Import data in FK-safe order
        print("\n📥 Loading lookup tables ...")
        import_regions(conn)
        import_groups(conn)
        import_locales(conn)
        import_directions(conn)

        conn.commit()
        print("\n🎉 Database initialization complete.")
    finally:
        conn.close()


if __name__ == "__main__":
    run()
