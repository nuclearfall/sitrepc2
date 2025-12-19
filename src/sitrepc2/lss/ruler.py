# src/sitrepc2/lss/ruler.py
from __future__ import annotations

import sqlite3
from collections import defaultdict
from typing import Dict, Iterable, List

from spacy.language import Language
from spacy.pipeline import EntityRuler

from sitrepc2.config.paths import gazetteer_path as gazetteer_db_path

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(get_gazetteer_db_path())
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    return con


def _load_aliases() -> Dict[str, List[str]]:
    """
    Load all aliases from the unified aliases VIEW.

    Returns:
        Mapping of entity_type -> list of normalized alias strings.
        entity_type values are expected to already be canonical
        (LOCATION, REGION, GROUP, DIRECTION).
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

        if isinstance(et, str) and isinstance(alias, str) and alias.strip():
            out[et].append(alias.strip())

    # Deduplicate per entity_type
    for et in out:
        out[et] = sorted(set(out[et]))

    return out


# ---------------------------------------------------------------------------
# Pattern builders
# ---------------------------------------------------------------------------

def _simple_alias_patterns(
    aliases: Iterable[str],
    label: str,
) -> List[dict]:
    """
    Build token-based EntityRuler patterns for exact phrase matching.

    Aliases are assumed to already be normalized (lowercase).
    """
    patterns: List[dict] = []

    for alias in aliases:
        tokens = alias.split()

        pattern = [{"LOWER": t} for t in tokens]

        patterns.append(
            {
                "label": label,
                "pattern": pattern,
                "id": f"{label}:{alias}",
            }
        )

    return patterns


# ---------------------------------------------------------------------------
# EntityRuler management
# ---------------------------------------------------------------------------

def _ensure_entity_ruler(nlp: Language) -> EntityRuler:
    """
    Ensure a clean EntityRuler exists and is configured
    to overwrite default NER entities.
    """
    # Remove existing custom ruler if present
    if "custom_entity_ruler" in nlp.pipe_names:
        nlp.remove_pipe("custom_entity_ruler")

    # Insert after NER if present (so we overwrite it)
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
    ruler.ent_id_sep = "|"

    return ruler


def _install_patterns(nlp: Language) -> Language:
    """
    Install DB-backed EntityRuler patterns from gazetteer aliases.
    """
    ruler = _ensure_entity_ruler(nlp)

    aliases_by_entity = _load_aliases()

    total_patterns = 0

    print("\n" + "=" * 60)
    print("ENTITY RULER PATTERN LOADING")
    print("=" * 60)

    for entity_type, aliases in aliases_by_entity.items():
        patterns = _simple_alias_patterns(aliases, entity_type)
        ruler.add_patterns(patterns)
        total_patterns += len(patterns)

        print(f"✓ {entity_type:<9} patterns: {len(patterns)}")

    print(f"Total patterns loaded: {total_patterns}")
    print("=" * 60 + "\n")

    return nlp


# ---------------------------------------------------------------------------
# Public entry point (used by LSS)
# ---------------------------------------------------------------------------

def add_entity_rulers_from_db(nlp: Language) -> Language:
    """
    Install DB-backed EntityRuler patterns for LSS.

    Emits canonical uppercase entity labels:
        LOCATION, REGION, GROUP, DIRECTION
    """
    return _install_patterns(nlp)
