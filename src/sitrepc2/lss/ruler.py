# src/sitrepc2/lss/ruler.py
from __future__ import annotations

import sqlite3
from collections import defaultdict
from typing import Dict, Iterable, List

from spacy.language import Language
from spacy.pipeline import EntityRuler

from sitrepc2.config.paths import gazetteer_path


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(gazetteer_path())
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    return con


def _load_aliases() -> Dict[str, List[str]]:
    """
    Load canonical, normalized aliases.

    Contract:
    - Returns lowercase, whitespace-normalized strings
    - Emits NO semantic meaning
    """
    out: Dict[str, List[str]] = defaultdict(list)

    with _conn() as con:
        rows = con.execute(
            """
            SELECT entity_type, normalized
            FROM aliases
            WHERE normalized IS NOT NULL
            """
        ).fetchall()

    for row in rows:
        et = row["entity_type"]
        alias = row["normalized"]

        if not isinstance(et, str) or not isinstance(alias, str):
            continue

        norm = " ".join(alias.lower().split())
        if norm:
            out[et].append(norm)

    for et in out:
        out[et] = sorted(set(out[et]))

    return out


def _simple_alias_patterns(
    aliases: Iterable[str],
    label: str,
) -> List[dict]:
    """
    Build exact-token EntityRuler patterns.

    IDs are intentionally opaque.
    """
    patterns: List[dict] = []

    for alias in aliases:
        tokens = alias.split()
        pattern = [{"LOWER": t} for t in tokens]

        patterns.append(
            {
                "label": label,
                "pattern": pattern,
            }
        )

    return patterns


def _ensure_entity_ruler(nlp: Language) -> EntityRuler:
    if "custom_entity_ruler" in nlp.pipe_names:
        nlp.remove_pipe("custom_entity_ruler")

    if "ner" in nlp.pipe_names:
        ruler = nlp.add_pipe(
            "entity_ruler",
            after="ner",
            name="custom_entity_ruler",
        )
    else:
        ruler = nlp.add_pipe(
            "entity_ruler",
            name="custom_entity_ruler",
        )

    ruler.overwrite = True
    return ruler


def _install_patterns(nlp: Language) -> Language:
    ruler = _ensure_entity_ruler(nlp)
    aliases_by_entity = _load_aliases()

    for entity_type, aliases in aliases_by_entity.items():
        ruler.add_patterns(
            _simple_alias_patterns(aliases, entity_type)
        )

    return nlp


def add_entity_rulers_from_db(nlp: Language) -> Language:
    """
    Install DB-backed EntityRuler patterns.

    Emits ONLY:
        LOCATION, REGION, GROUP, DIRECTION
    """
    return _install_patterns(nlp)
