# src/sitrepc2/cli/lss_cmd.py
from __future__ import annotations

import sqlite3
from datetime import date
from typing import Optional, List, Dict, Set

import typer
from rich import print
from rich.table import Table

from sitrepc2.config.paths import records_path as records_db_path

app = typer.Typer(help="Query LSS-layer outputs (read-only).")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(records_db_path())
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    return con


def _parse_date_iso(value: str) -> tuple[str, str]:
    try:
        d = date.fromisoformat(value)
    except ValueError:
        raise typer.BadParameter("Date must be YYYY-MM-DD")

    start = f"{d.isoformat()}T00:00:00Z"
    end = f"{d.isoformat()}T23:59:59Z"
    return start, end


def _validate_selectors(
    *,
    post_id: Optional[int],
    alias: Optional[str],
    publisher: Optional[str],
    pub_date: Optional[str],
    source: Optional[str],
):
    if post_id is not None:
        if any([alias, publisher, pub_date, source]):
            raise typer.BadParameter(
                "--post-id cannot be combined with other filters."
            )
    else:
        if not any([alias, publisher, pub_date, source]):
            raise typer.BadParameter(
                "At least one of --pub-date, --alias, --publisher, or --source must be provided."
            )


def _select_ingest_posts(
    *,
    con: sqlite3.Connection,
    post_id: Optional[int],
    alias: Optional[str],
    publisher: Optional[str],
    pub_date: Optional[str],
    source: Optional[str],
    limit: Optional[int],
) -> List[sqlite3.Row]:

    clauses: List[str] = []
    params: List[object] = []

    if post_id is not None:
        clauses.append("id = ?")
        params.append(post_id)

    if alias is not None:
        clauses.append("alias = ?")
        params.append(alias)

    if publisher is not None:
        clauses.append("publisher = ?")
        params.append(publisher)

    if source is not None:
        clauses.append("source = ?")
        params.append(source)

    if pub_date is not None:
        start, end = _parse_date_iso(pub_date)
        clauses.append("published_at BETWEEN ? AND ?")
        params.extend([start, end])

    where_sql = " AND ".join(clauses)

    sql = f"""
        SELECT id, published_at, alias, publisher, source
        FROM ingest_posts
        WHERE {where_sql}
        ORDER BY published_at ASC
    """

    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)

    return con.execute(sql, params).fetchall()


def _latest_run(con: sqlite3.Connection, ingest_post_id: int) -> Optional[sqlite3.Row]:
    return con.execute(
        """
        SELECT *
        FROM lss_runs
        WHERE ingest_post_id = ?
          AND completed_at IS NOT NULL
        ORDER BY completed_at DESC
        LIMIT 1
        """,
        (ingest_post_id,),
    ).fetchone()


# ---------------------------------------------------------------------------
# EVENTS COMMAND (unchanged behavior)
# ---------------------------------------------------------------------------

@app.command("events")
def lss_events(
    *,
    post_id: Optional[int] = typer.Option(None),
    alias: Optional[str] = typer.Option(None),
    publisher: Optional[str] = typer.Option(None),
    pub_date: Optional[str] = typer.Option(None),
    source: Optional[str] = typer.Option(None),
    limit: Optional[int] = typer.Option(None),
):
    """Inspect raw LSS structural outputs (events, roles, contexts)."""

    _validate_selectors(
        post_id=post_id,
        alias=alias,
        publisher=publisher,
        pub_date=pub_date,
        source=source,
    )

    with _conn() as con:
        posts = _select_ingest_posts(
            con=con,
            post_id=post_id,
            alias=alias,
            publisher=publisher,
            pub_date=pub_date,
            source=source,
            limit=limit,
        )

        if not posts:
            print("[yellow]No matching ingest posts found.[/yellow]")
            raise typer.Exit()

        print(f"[green]Found {len(posts)} ingest post(s)[/green]")

        for post in posts:
            _render_post(con, post)


# ---------------------------------------------------------------------------
# SUMMARIZE COMMAND (new)
# ---------------------------------------------------------------------------

@app.command("summarize")
def lss_summarize(
    *,
    post_id: Optional[int] = typer.Option(None),
    alias: Optional[str] = typer.Option(None),
    publisher: Optional[str] = typer.Option(None),
    pub_date: Optional[str] = typer.Option(None),
    source: Optional[str] = typer.Option(None),
    limit: Optional[int] = typer.Option(None),
):
    """
    Summarize Holmes + entity-ruler signals:
    actors, actions, locations, and contextual spans.
    """

    _validate_selectors(
        post_id=post_id,
        alias=alias,
        publisher=publisher,
        pub_date=pub_date,
        source=source,
    )

    with _conn() as con:
        posts = _select_ingest_posts(
            con=con,
            post_id=post_id,
            alias=alias,
            publisher=publisher,
            pub_date=pub_date,
            source=source,
            limit=limit,
        )

        if not posts:
            print("[yellow]No matching ingest posts found.[/yellow]")
            raise typer.Exit()

        for post in posts:
            run = _latest_run(con, post["id"])
            if not run:
                continue

            # -------------------------
            # Events
            # -------------------------
            events = con.execute(
                "SELECT id FROM lss_events WHERE lss_run_id = ?",
                (run["id"],),
            ).fetchall()

            event_ids = [e["id"] for e in events]
            if not event_ids:
                continue

            # -------------------------
            # Holmes roles (collapsed)
            # -------------------------
            roles = con.execute(
                f"""
                SELECT role_kind, document_word
                FROM lss_role_candidates
                WHERE lss_event_id IN ({",".join("?" * len(event_ids))})
                """,
                event_ids,
            ).fetchall()

            actors = set()
            actions = set()
            locations = set()

            for r in roles:
                kind = (r["role_kind"] or "").lower()
                word = r["document_word"]

                if kind in {"subject", "object", "possessor"}:
                    actors.add(word)

                elif kind in {"verb"}:
                    actions.add(word)

                elif kind in {"prep_object"}:
                    locations.add(word)


            # -------------------------
            # Context spans (ruler output)
            # -------------------------
            contexts = con.execute(
                """
                SELECT ctx_kind, text
                FROM lss_context_spans
                WHERE lss_run_id = ?
                """,
                (run["id"],),
            ).fetchall()

            ctx_map: Dict[str, Set[str]] = {}
            for c in contexts:
                ctx_map.setdefault(c["ctx_kind"], set()).add(c["text"])

            # -------------------------
            # Output
            # -------------------------
            print()
            print(
                f"[bold cyan]Post {post['id']}[/bold cyan] "
                f"{post['published_at']} | {post['alias']} | {post['publisher']}"
            )
            print(f"  Events: {len(events)}")

            if actors:
                print(f"  Actors: {', '.join(sorted(actors))}")
            if actions:
                print(f"  Actions: {', '.join(sorted(actions))}")
            if locations:
                print(f"  Locations: {', '.join(sorted(locations))}")

            for kind in ("GROUP", "DIRECTION", "REGION", "LOCATION"):
                values = ctx_map.get(kind)
                if values:
                    print(f"  {kind}: {', '.join(sorted(values))}")



# ---------------------------------------------------------------------------
# Rendering helpers (events)
# ---------------------------------------------------------------------------

def _render_post(con: sqlite3.Connection, post: sqlite3.Row) -> None:
    print()
    print(
        f"[bold cyan]Post {post['id']}[/bold cyan] "
        f"{post['published_at']} | {post['alias']} | {post['publisher']}"
    )

    run = _latest_run(con, post["id"])
    if not run:
        print("[yellow]  No completed LSS run.[/yellow]")
        return

    print(
        f"  [green]LSS run {run['id']}[/green] "
        f"({run['engine']} {run['engine_version']})"
    )

    _render_events(con, run["id"])
    _render_contexts(con, run["id"])


def _render_events(con: sqlite3.Connection, run_id: int) -> None:
    events = con.execute(
        """
        SELECT *
        FROM lss_events
        WHERE lss_run_id = ?
        ORDER BY ordinal ASC
        """,
        (run_id,),
    ).fetchall()

    if not events:
        print("  [yellow]No events extracted.[/yellow]")
        return

    table = Table(title="Events", show_lines=True)
    table.add_column("ID", style="cyan", width=6)
    table.add_column("Label", style="green")
    table.add_column("Neg", width=3)
    table.add_column("Unc", width=3)
    table.add_column("Text")

    for ev in events:
        table.add_row(
            str(ev["id"]),
            ev["label"],
            "Y" if ev["negated"] else "",
            "Y" if ev["uncertain"] else "",
            ev["text"][:120] + ("…" if len(ev["text"]) > 120 else ""),
        )

    print(table)

    for ev in events:
        _render_roles(con, ev["id"])


def _render_roles(con: sqlite3.Connection, event_id: int) -> None:
    roles = con.execute(
        """
        SELECT *
        FROM lss_role_candidates
        WHERE lss_event_id = ?
        ORDER BY role_kind ASC
        """,
        (event_id,),
    ).fetchall()

    if not roles:
        return

    table = Table(title=f"Roles for event {event_id}", show_lines=False)
    table.add_column("Kind", style="cyan")
    table.add_column("Word", style="green")
    table.add_column("Neg")
    table.add_column("Unc")

    for r in roles:
        table.add_row(
            r["role_kind"],
            r["document_word"],
            "Y" if r["negated"] else "",
            "Y" if r["uncertain"] else "",
        )

    print(table)


def _render_contexts(con: sqlite3.Connection, run_id: int) -> None:
    rows = con.execute(
        """
        SELECT *
        FROM lss_context_spans
        WHERE lss_run_id = ?
        ORDER BY ctx_kind ASC
        """,
        (run_id,),
    ).fetchall()

    if not rows:
        return

    table = Table(title="Context spans", show_lines=False)
    table.add_column("Kind", style="cyan")
    table.add_column("Text")

    for r in rows:
        table.add_row(r["ctx_kind"], r["text"])

    print(table)
