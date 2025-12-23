# src/sitrepc2/cli/app.py

from __future__ import annotations
import typer

from .init_cmd import app as init_app
# from .db_cmd import app as db_app
# from .source_cmd import app as source_app
from .lss_cmd import app as lss_app

from .fetch_cmd import fetch_callback as fetch
from .extract_cmd import extract_callback as extract

app = typer.Typer(help="sitrepc2 command line interface")

# namespaces
app.add_typer(init_app, name="init")
# app.add_typer(db_app, name="db")
# app.add_typer(source_app, name="source")
app.add_typer(lss_app, name="lss")

# standalone verbs
app.command("fetch")(fetch)
app.command("extract")(extract)
