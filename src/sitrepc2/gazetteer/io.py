# src/sitrepc2/gazetteer/io.py
from __future__ import annotations

import csv
from pathlib import Path
from typing import List, Optional

from sitrepc2.gazetteer.typedefs import (
    LocaleEntry,
    RegionEntry,
    GroupEntry,
    DirectionEntry,
)
from sitrepc2.util.serialization import serialize, deserialize
from sitrepc2.util.encoding import decode_coord_u64


# ------------------------------
# Alias helpers
# ------------------------------

def unpack_aliases(s: str | None) -> List[str]:
    if not s:
        return []
    return [a.strip() for a in s.split(";") if a.strip()]


def pack_aliases(aliases: List[str]) -> str:
    return ";".join(a for a in aliases if a.strip())


# ------------------------------
# Locale Loader
# ------------------------------

def load_locales(path: Path) -> List[LocaleEntry]:
    out: List[LocaleEntry] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["aliases"] = unpack_aliases(row.get("aliases"))
            row["lon"] = float(row["lon"])
            row["lat"] = float(row["lat"])
            row["cid"] = int(row["cid"])
            out.append(deserialize(row, LocaleEntry))
    return out


# ------------------------------
# Region Loader
# ------------------------------

def load_regions(path: Path) -> List[RegionEntry]:
    out: List[RegionEntry] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["aliases"] = unpack_aliases(row.get("aliases"))
            row["neighbors"] = unpack_aliases(row.get("neighbors"))
            out.append(deserialize(row, RegionEntry))
    return out


# ------------------------------
# Group Loader
# ------------------------------

def load_groups(path: Path) -> List[GroupEntry]:
    out: List[GroupEntry] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["aliases"] = unpack_aliases(row.get("aliases"))
            row["regions"] = unpack_aliases(row.get("regions"))
            row["neighbors"] = unpack_aliases(row.get("neighbors"))
            row["group_id"] = int(row["group_id"])
            out.append(deserialize(row, GroupEntry))
    return out


# ------------------------------
# Direction Loader
# ------------------------------

def load_directions(path: Path, locales: List[LocaleEntry]) -> List[DirectionEntry]:
    out: List[DirectionEntry] = []
    locale_by_cid = {loc.cid: loc for loc in locales}

    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            anchor_cid = int(row["anchor"])
            anchor = locale_by_cid.get(anchor_cid)
            if anchor is None:
                raise ValueError(f"Direction anchor CID {anchor_cid} not found in locales")

            row["aliases"] = unpack_aliases(row.get("aliases"))
            row["anchor"] = anchor
            out.append(deserialize(row, DirectionEntry))

    return out


# ------------------------------
# Patch loader / saver
# ------------------------------

def load_patch(path: Path) -> List[LocaleEntry]:
    out = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["aliases"] = unpack_aliases(row.get("aliases"))
            row["lon"] = float(row["lon"])
            row["lat"] = float(row["lat"])
            row["cid"] = int(row["cid"])
            out.append(deserialize(row, LocaleEntry))
    return out
