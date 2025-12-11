# scripts/init_db.py
from __future__ import annotations

import sqlite3
from pathlib import Path

from sitrepc2.config.paths import current_dotpath
from .import_region_lookup import import_regions
from .import_group_lookup import import_groups
from .import_locale_lookup import import_locales
from .import_direction_lookup import import_directions


def run():
    dot = current_dotpath()
    db_path = dot / "sitrepc2.db"
    schema_path = Path(__file__).parent / "schema.sql"

    print(f"📦 Initializing database: {db_path}")
    conn = sqlite3.connect(db_path)

    # apply schema
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    print("✔ Schema applied.")

    import_regions(conn)
    import_groups(conn)
    import_locales(conn)
    import_directions(conn)

    conn.commit()
    conn.close()
    print("\n🎉 Database initialization complete.")


if __name__ == "__main__":
    run()
