# src/sitrepc2/nlp/rulers.py
from __future__ import annotations
from pathlib import Path
from typing import List, Set
import csv

from spacy.language import Language
from spacy.pipeline import EntityRuler

from sitrepc2.config.paths import gazetteer_paths
from sitrepc2.util.normalize import normalize_location_key
from sitrepc2.gazetteer.aliases import gather_aliases
from sitrepc2.gazetteer.typedefs import LocaleEntry, RegionEntry, GroupEntry, DirectionEntry


# -----------------------------
# Helpers
# -----------------------------

def _simple_alias_patterns(aliases: Set[str], label: str) -> List[dict]:
    """
    Produce simple exact-match patterns (case-insensitive automatically in spaCy).
    Used for LOCALE, REGION, GROUP.
    """
    return [{"label": label, "pattern": alias} for alias in sorted(aliases)]


def _direction_phrase_patterns(aliases: Set[str]) -> List[dict]:
    """
    Produce LOWER-token patterns for directions for:
        - in the direction of X
        - towards X
        - X direction
        - X axis
        - X sector
        - the X line
    """
    patterns = []

    for alias in sorted(aliases):
        norm = normalize_location_key(alias)

        # Token-based case-insensitive patterns
        patterns.extend([
            # in the direction of X
            {
                "label": "DIRECTION",
                "pattern": [
                    {"LOWER": "in"},
                    {"LOWER": "the"},
                    {"LOWER": "direction"},
                    {"LOWER": "of"},
                    {"LOWER": norm}
                ]
            },
            # towards X
            {
                "label": "DIRECTION",
                "pattern": [
                    {"LOWER": "towards"},
                    {"LOWER": norm}
                ]
            },
            # X direction
            {
                "label": "DIRECTION",
                "pattern": [
                    {"LOWER": norm},
                    {"LOWER": "direction"}
                ]
            },
            # X axis
            {
                "label": "DIRECTION",
                "pattern": [
                    {"LOWER": norm},
                    {"LOWER": "axis"}
                ]
            },
            # X sector
            {
                "label": "DIRECTION",
                "pattern": [
                    {"LOWER": norm},
                    {"LOWER": "sector"}
                ]
            },
            # the X line
            {
                "label": "DIRECTION",
                "pattern": [
                    {"LOWER": "the"},
                    {"LOWER": norm},
                    {"LOWER": "line"}
                ]
            },
        ])

    return patterns


# -----------------------------
# Main entry point
# -----------------------------

def add_entity_rulers(
    nlp: Language,
    *,
    locales: List[LocaleEntry],
    regions: List[RegionEntry],
    groups: List[GroupEntry],
    directions: List[DirectionEntry],
) -> Language:
    """
    Install EntityRuler and populate it from:
        - locale aliases
        - region aliases
        - group aliases
        - direction aliases + direction phrase patterns
    """

    if "entity_ruler" in nlp.pipe_names:
        ruler = nlp.get_pipe("entity_ruler")
    else:
        if "ner" in nlp.pipe_names:
            ruler = nlp.add_pipe("entity_ruler", before="ner")
        else:
            ruler = nlp.add_pipe("entity_ruler")

    assert isinstance(ruler, EntityRuler)
    ruler.validate = True
    ruler.ent_id_sep = None

    # ---- Collect aliases from all gazetteer sources ----
    locale_aliases, region_aliases, group_aliases, direction_aliases = gather_aliases(
        locales, regions, groups, directions
    )

    # ---- LOCALE / REGION / GROUP patterns (simple string patterns) ----
    ruler.add_patterns(_simple_alias_patterns(set(locale_aliases), "LOCALE"))
    ruler.add_patterns(_simple_alias_patterns(set(region_aliases), "REGION"))
    ruler.add_patterns(_simple_alias_patterns(set(group_aliases), "GROUP"))

    # ---- DIRECTION patterns (token-based, case-insensitive) ----
    ruler.add_patterns(_direction_phrase_patterns(set(direction_aliases)))

    return nlp
