from __future__ import annotations

import typer
from typing import Optional
from rich import print
from rich.table import Table

from sitrepc2.db.core import connect
from sitrepc2.config.paths import current_db_path

app = typer.Typer(help="Query and inspect sitrepc2 SQLite database")


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def pretty_table(title: str, rows: list[dict]):
    if not rows:
        print(f"[yellow]No results for {title}[/yellow]")
        return

    table = Table(title=title)
    for col in rows[0].keys():
        table.add_column(col)

    for r in rows:
        table.add_row(*[str(r[c]) for c in r.keys()])
    print(table)


def normalize(s: str) -> str:
    return " ".join(s.strip().lower().split())


# ------------------------------------------------------------
# LIST COMMANDS
# ------------------------------------------------------------

@app.command("list")
def list_entities(entity: str):
    """
    List all entries of a specific entity type:

        sitrepc2 db list locales
        sitrepc2 db list regions
        sitrepc2 db list groups
        sitrepc2 db list directions
    """

    entity = entity.lower()
    conn = connect()

    if entity == "locales":
        rows = conn.execute("SELECT * FROM locales ORDER BY name ASC").fetchall()
        pretty_table("Locales", rows)
        return

    if entity == "regions":
        rows = conn.execute("SELECT * FROM regions ORDER BY name ASC").fetchall()
        pretty_table("Regions", rows)
        return

    if entity == "groups":
        rows = conn.execute("SELECT * FROM groups ORDER BY group_id ASC").fetchall()
        pretty_table("Groups", rows)
        return

    if entity == "directions":
        rows = conn.execute("SELECT * FROM directions ORDER BY name ASC").fetchall()
        pretty_table("Directions", rows)
        return

    print("[red]Unknown entity type. Use: locales | regions | groups | directions[/red]")


# ------------------------------------------------------------
# FIND COMMANDS
# ------------------------------------------------------------

@app.command("find")
def find(entity: str, query: str):
    """
    Unified search selector:

        sitrepc2 db find locale <query>
        sitrepc2 db find region <query>
        sitrepc2 db find group <query>
        sitrepc2 db find direction <query>
    """
    entity = entity.lower()

    if entity == "locale":
        return find_locale(query)
    if entity == "region":
        return find_region(query)
    if entity == "group":
        return find_group(query)
    if entity == "direction":
        return find_direction(query)

    print("[red]Unknown entity type. Use: locale | region | group | direction[/red]")


# ------------------------------------------------------------
# LOCALE FINDER
# ------------------------------------------------------------

def find_locale(query: str):
    conn = connect()
    norm = normalize(query)

    # 1. cid
    rows = conn.execute(
        "SELECT * FROM locales WHERE cid = ?", (query,)
    ).fetchall()
    if rows:
        pretty_table("Locales (cid)", rows)
        return

    # 2. numeric → locale.id or region_osm_id
    if query.isdigit():
        n = int(query)
        rows = conn.execute(
            "SELECT * FROM locales WHERE cid = ? OR region_osm_id = ?",
            (n, n),
        ).fetchall()
        if rows:
            pretty_table("Locales (id or region_osm_id)", rows)
            return

    # 3. wikidata
    rows = conn.execute(
        "SELECT * FROM locales WHERE wikidata = ?", (query,)
    ).fetchall()
    if rows:
        pretty_table("Locales (wikidata)", rows)
        return

    # 4. exact name
    rows = conn.execute(
        "SELECT * FROM locales WHERE name = ?", (query,)
    ).fetchall()
    if rows:
        pretty_table("Locales (name)", rows)
        return

    # 5. alias lookup
    rows = conn.execute(
        """
        SELECT l.*
        FROM aliases a
        JOIN locales l ON a.entity_id = l.cid
        WHERE a.entity_type='locale' AND a.normalized = ?
        """,
        (norm,),
    ).fetchall()
    pretty_table("Locales (aliases)", rows)


# ------------------------------------------------------------
# REGION FINDER
# ------------------------------------------------------------

def find_region(query: str):
    conn = connect()
    norm = normalize(query)

    if query.isdigit():
        n = int(query)
        rows = conn.execute(
            "SELECT * FROM regions WHERE osm_id = ? OR id = ?", (n, n)
        ).fetchall()
        if rows:
            pretty_table("Regions (osm_id or id)", rows)
            return

    rows = conn.execute(
        "SELECT * FROM regions WHERE wikidata = ?", (query,)
    ).fetchall()
    if rows:
        pretty_table("Regions (wikidata)", rows)
        return

    rows = conn.execute(
        "SELECT * FROM regions WHERE name = ?", (query,)
    ).fetchall()
    if rows:
        pretty_table("Regions (name)", rows)
        return

    rows = conn.execute(
        """
        SELECT r.*
        FROM aliases a
        JOIN regions r ON a.entity_id = r.id
        WHERE a.entity_type='region' AND a.normalized = ?
        """,
        (norm,),
    ).fetchall()
    pretty_table("Regions (aliases)", rows)


# ------------------------------------------------------------
# GROUP FINDER
# ------------------------------------------------------------

def find_group(query: str):
    conn = connect()
    norm = normalize(query)

    if query.isdigit():
        gid = int(query)
        rows = conn.execute(
            "SELECT * FROM groups WHERE group_id = ? OR id = ?", (gid, gid)
        ).fetchall()
        if rows:
            pretty_table("Groups (group_id or id)", rows)
            return

    rows = conn.execute(
        "SELECT * FROM groups WHERE name = ?", (query,)
    ).fetchall()
    if rows:
        pretty_table("Groups (name)", rows)
        return

    rows = conn.execute(
        """
        SELECT g.*
        FROM aliases a
        JOIN groups g ON a.entity_id = g.id
        WHERE a.entity_type='group' AND a.normalized = ?
        """,
        (norm,),
    ).fetchall()

    pretty_table("Groups (aliases)", rows)


# ------------------------------------------------------------
# DIRECTION FINDER
# ------------------------------------------------------------

def find_direction(query: str):
    conn = connect()
    norm = normalize(query)

    # directions do NOT use cid
    rows = conn.execute(
        "SELECT * FROM directions WHERE name = ?", (query,)
    ).fetchall()
    if rows:
        pretty_table("Directions (name)", rows)
        return

    # alias support (optional but included)
    rows = conn.execute(
        """
        SELECT d.*
        FROM aliases a
        JOIN directions d ON a.entity_id = d.id
        WHERE a.entity_type='direction' AND a.normalized = ?
        """,
        (norm,),
    ).fetchall()

    pretty_table("Directions (aliases)", rows)


# ------------------------------------------------------------
# SHOW COMMAND (unchanged except column fix)
# ------------------------------------------------------------

@app.command("show")
def show(entity: str, identifier: str):
    """
    Show full record for an entity.
    """

    conn = connect()

    if entity == "direction":
        row = conn.execute(
            "SELECT * FROM directions WHERE name = ?", (identifier,)
        ).fetchone()
        if not row:
            print("[red]Direction not found[/red]")
            return
        pretty_table("Direction", [row])
        return

    if entity == "locale":
        if identifier.isdigit():
            row = conn.execute(
                "SELECT * FROM locales WHERE id = ?", (int(identifier),)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM locales WHERE cid = ?", (identifier,)
            ).fetchone()

        if not row:
            print("[red]Locale not found[/red]")
            return

        pretty_table("Locale", [row])

        aliases = conn.execute(
            """
            SELECT alias, normalized
            FROM aliases
            WHERE entity_type='locale' AND entity_id=?
            """,
            (row["cid"],)
        ).fetchall()

        pretty_table("Aliases", aliases)
        return

    # other entity show cases unchanged…

    print("[red]Unknown entity for show command[/red]")
