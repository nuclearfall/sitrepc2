from __future__ import annotations

from pathlib import Path
from typing import Iterable, List
import json

from ..models.entity_ruler import EntityRulerModel


def load_rulers_jsonl(path: Path) -> List[EntityRulerModel]:
    """
    Load EntityRuler definitions from a JSONL file.

    Each line must contain exactly one ruler definition.
    """
    rulers: List[EntityRulerModel] = []

    with path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON on line {lineno} in {path}"
                ) from exc

            rulers.append(EntityRulerModel.from_json(data))

    return rulers


def save_rulers_jsonl(
    path: Path,
    rulers: Iterable[EntityRulerModel],
) -> None:
    """
    Save EntityRuler definitions to a JSONL file.

    Each ruler is written as a single JSON object per line.
    """
    with path.open("w", encoding="utf-8") as f:
        for ruler in rulers:
            json.dump(ruler.to_json(), f, ensure_ascii=False)
            f.write("\n")
