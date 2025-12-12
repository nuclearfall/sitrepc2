# src/sitrepc2/cli/app.py
from __future__ import annotations

import typer

from .init_cmd import app as init_app
from .db_cmd import app as db_app
from .source_cmd import app as source_app

# 🚨 IMPORT THE CALLBACK, NOT THE APP
from .fetch_cmd import fetch_callback as fetch

app = typer.Typer(help="sitrepc2 command line interface")

app.add_typer(init_app, name="init")
app.add_typer(db_app, name="db")
app.add_typer(source_app, name="source")

# ✔ register fetch as a command
app.command("fetch")(fetch)
