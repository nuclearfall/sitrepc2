from __future__ import annotations

from typing import Optional, Sequence, Mapping
import pathlib
import typer
from rich import print
from rich.table import Table

from sitrepc2.db.core import connect
from sitrepc2.config.paths import current_db_path

app = typer.Typer(help="Query and inspect sitrepc2 SQLite database")


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def pretty_table(title: str, rows: Sequence[Mapping]):
    """
    Render a Rich table from a sequence of row-like mappings
    (e.g. sqlite3.Row or dict).
    """
    if not rows:
        print(f"[yellow]No results for {title}[/yellow]")
        return

    first = rows[0]
    cols = list(first.keys())

    table = Table(title=title)
    for col in cols:
        table.add_column(col)

    for r in rows:
        table.add_row(*[str(r[c]) for c in cols])

    print(table)


def normalize(s: str) -> str:
    """Simple normalization used for alias lookups."""
    return " ".join(s.strip().lower().split())


# ------------------------------------------------------------
# INFO COMMAND
# ------------------------------------------------------------

@app.command("info")
def info():
    """
    Show high-level information about the sitrepc2 database:

      - DB file path
      - Table list and row counts
      - PRAGMA integrity_check
      - Basic foreign key sanity checks for the main tables
    """
    db_path = current_db_path()
    print(f"[cyan]Database path:[/cyan] {db_path}")

    conn = connect()
    try:
        # ----------------------------
        # Table list + row counts
        # ----------------------------
        tables = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()

        if not tables:
            print("[yellow]No user tables found in this database.[/yellow]")
        else:
            table = Table(title="Table counts")
            table.add_column("table")
            table.add_column("rows", justify="right")

            for row in tables:
                name = row["name"]
                count = conn.execute(
                    f"SELECT COUNT(*) AS n FROM {name}"
                ).fetchone()["n"]
                table.add_row(name, str(count))

            print(table)

        # ----------------------------
        # PRAGMA integrity_check
        # ----------------------------
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity == "ok":
            print("[green]PRAGMA integrity_check: ok[/green]")
        else:
            print(f"[red]PRAGMA integrity_check: {integrity}[/red]")

        # ----------------------------
        # FK sanity checks
        # ----------------------------

        # 1) locales.region_id → regions.osm_id
        orphan_region = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM locales l
            LEFT JOIN regions r ON l.region_id = r.osm_id
            WHERE l.region_id IS NOT NULL
              AND r.osm_id IS NULL
            """
        ).fetchone()["n"]

        if orphan_region == 0:
            print("[green]FK check:[/green] locales.region_id → regions.osm_id [ok]")
        else:
            print(
                f"[red]FK check:[/red] locales.region_id → regions.osm_id "
                f"[bold]{orphan_region}[/bold] orphan row(s)"
            )

        # 2) locales.group_id → groups.group_id
        orphan_group = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM locales l
            LEFT JOIN groups g ON l.group_id = g.group_id
            WHERE l.group_id IS NOT NULL
              AND g.group_id IS NULL
            """
        ).fetchone()["n"]

        if orphan_group == 0:
            print("[green]FK check:[/green] locales.group_id → groups.group_id [ok]")
        else:
            print(
                f"[red]FK check:[/red] locales.group_id → groups.group_id "
                f"[bold]{orphan_group}[/bold] orphan row(s)"
            )

        # 3) directions.anchor_cid → locales.cid
        orphan_anchor = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM directions d
            LEFT JOIN locales l ON d.anchor_cid = l.cid
            WHERE d.anchor_cid IS NOT NULL
              AND l.cid IS NULL
            """
        ).fetchone()["n"]

        if orphan_anchor == 0:
            print("[green]FK check:[/green] directions.anchor_cid → locales.cid [ok]")
        else:
            print(
                f"[red]FK check:[/red] directions.anchor_cid → locales.cid "
                f"[bold]{orphan_anchor}[/bold] orphan row(s)"
            )

    finally:
        conn.close()
        
# ------------------------------------------------------------
# LIST COMMANDS
# ------------------------------------------------------------

@app.command("list")
def list_entities(
    entity: str = typer.Argument(..., help="locales | regions | groups | directions"),
    limit: int = typer.Option(
        50,
        "--limit",
        "-n",
        help="Maximum number of rows to display (0 = no limit).",
    ),
):
    """
    List entries of a specific entity type:

        sitrepc2 db list locales
        sitrepc2 db list regions
        sitrepc2 db list groups
        sitrepc2 db list directions

    Use --limit 0 to disable row limiting.
    """
    entity = entity.lower()
    conn = connect()
    limit_clause = "" if limit == 0 else f" LIMIT {int(limit)}"

    if entity == "locales":
        rows = conn.execute(
            "SELECT * FROM locales ORDER BY name ASC" + limit_clause
        ).fetchall()
        pretty_table("Locales", rows)
        return

    if entity == "regions":
        rows = conn.execute(
            "SELECT * FROM regions ORDER BY name ASC" + limit_clause
        ).fetchall()
        pretty_table("Regions", rows)
        return

    if entity == "groups":
        rows = conn.execute(
            "SELECT * FROM groups ORDER BY group_id ASC" + limit_clause
        ).fetchall()
        pretty_table("Groups", rows)
        return

    if entity == "directions":
        rows = conn.execute(
            "SELECT * FROM directions ORDER BY name ASC" + limit_clause
        ).fetchall()
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
    """
    Search order:

      1. Exact cid
      2. If numeric: region_id or group_id
      3. wikidata
      4. exact name
      5. alias (via aliases table, entity_type='locale')
    """
    conn = connect()
    norm = normalize(query)

    # 1. cid (primary key)
    rows = conn.execute(
        "SELECT * FROM locales WHERE cid = ?", (query,)
    ).fetchall()
    if rows:
        pretty_table("Locales (cid)", rows)
        return

    # 2. numeric → region_id or group_id
    if query.isdigit():
        n = int(query)
        rows = conn.execute(
            """
            SELECT * FROM locales
            WHERE region_id = ? OR group_id = ?
            """,
            (n, n),
        ).fetchall()
        if rows:
            pretty_table("Locales (region_id/group_id)", rows)
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

    # 5. alias lookup (only locales use aliases in current schema)
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
    """
    Search order:

      1. osm_id (numeric)
      2. wikidata
      3. exact name
    """
    conn = connect()

    # 1. osm_id (primary key)
    if query.isdigit():
        n = int(query)
        rows = conn.execute(
            "SELECT * FROM regions WHERE osm_id = ?", (n,)
        ).fetchall()
        if rows:
            pretty_table("Regions (osm_id)", rows)
            return

    # 2. wikidata
    rows = conn.execute(
        "SELECT * FROM regions WHERE wikidata = ?", (query,)
    ).fetchall()
    if rows:
        pretty_table("Regions (wikidata)", rows)
        return

    # 3. exact name
    rows = conn.execute(
        "SELECT * FROM regions WHERE name = ?", (query,)
    ).fetchall()
    pretty_table("Regions (name)", rows)


# ------------------------------------------------------------
# GROUP FINDER
# ------------------------------------------------------------

def find_group(query: str):
    """
    Search order:

      1. group_id (numeric)
      2. exact name
    """
    conn = connect()

    # 1. group_id (primary key)
    if query.isdigit():
        gid = int(query)
        rows = conn.execute(
            "SELECT * FROM groups WHERE group_id = ?", (gid,)
        ).fetchall()
        if rows:
            pretty_table("Groups (group_id)", rows)
            return

    # 2. exact name
    rows = conn.execute(
        "SELECT * FROM groups WHERE name = ?", (query,)
    ).fetchall()
    pretty_table("Groups (name)", rows)


# ------------------------------------------------------------
# DIRECTION FINDER
# ------------------------------------------------------------

def find_direction(query: str):
    """
    Search order:

      1. dir_id (numeric)
      2. exact name
    """
    conn = connect()

    # 1. dir_id
    if query.isdigit():
        dir_id = int(query)
        rows = conn.execute(
            "SELECT * FROM directions WHERE dir_id = ?", (dir_id,)
        ).fetchall()
        if rows:
            pretty_table("Directions (dir_id)", rows)
            return

    # 2. name
    rows = conn.execute(
        "SELECT * FROM directions WHERE name = ?", (query,)
    ).fetchall()
    pretty_table("Directions (name)", rows)


# ------------------------------------------------------------
# SHOW COMMAND
# ------------------------------------------------------------

@app.command("show")
def show(entity: str, identifier: str):
    """
    Show full record for an entity.

    Examples:

        sitrepc2 db show locale <cid>
        sitrepc2 db show region <osm_id>
        sitrepc2 db show group <group_id>
        sitrepc2 db show direction <dir_id or name>
    """
    entity = entity.lower()
    conn = connect()

    # --- Direction: allow dir_id or name
    if entity == "direction":
        if identifier.isdigit():
            row = conn.execute(
                """
                SELECT d.*, l.name AS anchor_name
                FROM directions d
                LEFT JOIN locales l ON l.cid = d.anchor_cid
                WHERE d.dir_id = ?
                """,
                (int(identifier),),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT d.*, l.name AS anchor_name
                FROM directions d
                LEFT JOIN locales l ON l.cid = d.anchor_cid
                WHERE d.name = ?
                """,
                (identifier,),
            ).fetchone()

        if not row:
            print("[red]Direction not found[/red]")
            return

        pretty_table("Direction", [row])
        return

    # --- Locale: show by cid only (primary key)
    if entity == "locale":
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
            (row["cid"],),
        ).fetchall()

        pretty_table("Aliases", aliases)
        return

    # --- Region: by osm_id
    if entity == "region":
        if not identifier.isdigit():
            print("[red]Region identifier must be an osm_id (integer)[/red]")
            return

        row = conn.execute(
            "SELECT * FROM regions WHERE osm_id = ?", (int(identifier),)
        ).fetchone()

        if not row:
            print("[red]Region not found[/red]")
            return

        pretty_table("Region", [row])
        return

    # --- Group: by group_id
    if entity == "group":
        if not identifier.isdigit():
            print("[red]Group identifier must be a group_id (integer)[/red]")
            return

        row = conn.execute(
            "SELECT * FROM groups WHERE group_id = ?", (int(identifier),)
        ).fetchone()

        if not row:
            print("[red]Group not found][/red]")
            return

        pretty_table("Group", [row])
        return

    print("[red]Unknown entity for show command[/red]")

# ------------------------------------------------------------
# SQL COMMAND (new)
# ------------------------------------------------------------

@app.command("sql")
def sql(
    query: str = typer.Argument(
        "",
        help="SQL to execute. If omitted, you must provide --file.",
    ),
    file: pathlib.Path = typer.Option(
        None,
        "--file",
        "-f",
        help="Read SQL from a file instead of the CLI argument.",
    ),
    title: str = typer.Option(
        "SQL result",
        "--title",
        help="Title for the result table when the query returns rows.",
    ),
):
    """
    Execute arbitrary SQL against the sitrepc2 database.

    Examples:

        # Simple SELECT
        sitrepc2 db sql "SELECT cid, name FROM locales LIMIT 10"

        # Show all table names
        sitrepc2 db sql "SELECT name FROM sqlite_master WHERE type='table'"

        # From a file
        sitrepc2 db sql --file debug.sql
    """
    if not query and not file:
        raise typer.BadParameter("You must provide a query or --file.")

    # Load SQL text
    sql_text = ""
    if file is not None:
        try:
            sql_text = file.read_text(encoding="utf-8")
        except OSError as e:
            print(f"[red]Could not read SQL file:[/red] {e}")
            raise typer.Exit(code=1)

    if query:
        # If both are provided, append the inline query after the file contents.
        sql_text = (sql_text + "\n" + query).strip()
    else:
        sql_text = sql_text.strip()

    if not sql_text:
        print("[yellow]No SQL to execute.[/yellow]")
        raise typer.Exit(code=0)

    conn = connect()
    cur = conn.cursor()

    # For now, we treat this as a single statement; multi-statement scripts should
    # typically go in a file and be split/managed manually if you need results back.
    try:
        cur.execute(sql_text)

        if cur.description:
            # Query returned rows (SELECT, PRAGMA, etc.)
            rows = cur.fetchall()
            if rows:
                # Reuse existing pretty_table helper
                pretty_table(title, rows)
            else:
                print("[yellow]Query executed successfully but returned no rows.[/yellow]")
        else:
            # Non-SELECT: commit and show rows affected
            conn.commit()
            affected = cur.rowcount
            print(f"[green]OK[/green] [dim]({affected} row(s) affected)[/dim]")

    except Exception as e:
        print(f"[red]SQL error:[/red] {e}")
        raise typer.Exit(code=1)
    finally:
        conn.close()
