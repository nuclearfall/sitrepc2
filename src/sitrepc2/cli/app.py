# src/sitrepc2/cli/app.py
from __future__ import annotations

import typer

from .init_cmd import app as init_app

app = typer.Typer(help="sitrepc2 command line interface")

app.add_typer(init_app, name="init")
