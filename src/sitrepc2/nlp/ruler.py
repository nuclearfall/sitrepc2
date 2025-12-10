# src/sitrepc2/nlp/__init__.py  (or wherever you put it)
from __future__ import annotations
from typing import Sequence, Tuple
from pathlib import Path
import csv

from spacy.language import Language
from spacy.pipeline import EntityRuler
from sitrepc2.config.paths import gazetteer_paths


def add_entity_rulers(
    nlp: Language,
    default_aliases_field: str = "aliases",
) -> Language:
    """
    Attach an EntityRuler and populate it from:
    - locale/region gazetteer_paths() (LOCALE, REGION)
    - optional other_entity triples (csvs, labels, fields).
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

    locale_csv, region_csv, group_csv = gazetteer_paths()

    paths: list[Path] = [Path(locale_csv), Path(region_csv), Path(group_csv)]
    labels: list[str] = ["LOCALE", "REGION", "GROUP"]
    fields: list[str] = [default_aliases_field, default_aliases_field, default_aliases_field]

    for path, label, field in zip(paths, labels, fields):
        aliases = _aliases_from_csv(path, aliases_field=field)
        if not aliases:
            continue
        patterns = [{"label": label, "pattern": name} for name in sorted(aliases)]
        ruler.add_patterns(patterns)

    return nlp


def _aliases_from_csv(path: Path, *, aliases_field: str = "aliases") -> set[str]:
    names: set[str] = set()

    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or aliases_field not in reader.fieldnames:
            return names
        for row in reader:
            raw = (row.get(aliases_field) or "").strip()
            if not raw:
                continue
            for part in raw.split(";"):
                alias = part.strip()
                if alias:
                    names.add(alias)

    return names
