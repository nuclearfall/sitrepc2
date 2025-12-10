"""Utilities for appending Russian exonyms to the reference gazetteer.

The helpers in this module are adapted from the mod-mymap tooling and are
focused on augmenting ``src/sitrepc2/reference/locale_lookup.csv`` with
Russian exonyms and their English transliterations.
"""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict

from sitrepc2.util.normalize import normalize_location_key

# ---------------------------------------------------------------------------
# Exonym maps (UA romanized -> RU-style romanized)
# ---------------------------------------------------------------------------

# Full-name exonyms that don’t follow simple word-level rules.
# Keys:  romanized Ukrainian name (lowercase, spaces)
# Values: Russian-style English exonym (lowercase; semicolon-separated if multiple)
FULL_NAME_EXONYM_MAP: Dict[str, str] = {
    # --- Capital & largest cities ---
    "kyiv": "kiev",
    "kharkiv": "kharkov",
    "odesa": "odessa",
    "dnipro": "dnepr;dnepropetrovsk",
    # --- Oblast capitals & big cities with strong Russian exonyms ---
    "zaporizhzhia": "zaporozhye;zaporizhia;aleksandrovsk",
    "mykolaiv": "nikolaev",
    "luhansk": "lugansk",
    "donetsk": "donetsk",
    "kherson": "kherson",
    "sumy": "sumy",
    "poltava": "poltava",
    "vinnytsia": "vinnitsa",
    "zhytomyr": "zhitomir",
    "chernihiv": "chernigov",
    "cherkasy": "cherkassy",
    "rivne": "rovno",
    "ivano-frankivsk": "ivano-frankovsk",
    "uzhhorod": "uzhgorod",
    "ternopil": "ternopol",
    "chernivtsi": "chernovtsy",
    "kropyvnytskyi": "kirovograd;elizabethgrad",
    # --- Decommunized industrial city with very strong Russian exonym ---
    "kamianske": "dniprodzerzhinsk;dniprodzerzhynsk;dneprodzerzhinsk",
    # --- Crimea & Sevastopol ---
    "simferopol": "simferopol",
    "sevastopol": "sevastopol",
    # --- Larger industrial cities / well-known exonyms ---
    "kryvyi rih": "krivoy rog",
    "kremenchuk": "kremenchug",
    "nikopol": "nikopol",
    "mariupol": "mariupol",
    "sloviansk": "slovyansk;slavyansk;slaviansk",
    "lyman": "liman;krasnyi lyman;krasny liman",
    "pokrovsk": "krasnoarmeysk;krasnoarmiysk",
    # --- A few historically important or common exonyms ---
    "izium": "izyum",
    "izyum": "izyum",
    # --- Decommunized towns/cities (7+2 oblast scope) ---
    "bakhmut": "artemivsk;artyomovsk;artemovsk",
    "toretsk": "dzerzhynsk;dzerzhinsk",
    "kalmiuske": "komsomolske;komsomolskoye",
    "myrnohrad": "mirnograd",
    # Luhansk Oblast
    "khrustalnyi": "krasnyi luch;krasny luch",
    "dovzhansk": "sverdlovsk",
    "kadiivka": "stakhanov",
    "sorokyne": "krasnodon",
    "voznesenivka": "chervonyi partyzan;chervony partizan;krasny partizan",
    # Dnipropetrovsk Oblast
    "pokrov": "ordzhonikidze",
    # Sumy Oblast
    "esman": "chervone",
    # Kherson Oblast
    "lazurne": "komsomolske;komsomolskoye",
}

# Word-level substitutions (safe & common in toponyms)
WORD_EXONYM_MAP: Dict[str, str] = {
    "mykolaivka": "nikolayevka",
    "mykolaiv": "nikolayev",
    "novomykolaivka": "novonikolayevka",
    "stara mykolaivka": "staraya nikolayevka",
    "mykhailivka": "mikhaylovka",
    "mykhailiv": "mikhaylov",
    # Common adjectives / prefixes
    "stara": "staraya",
    "staryi": "stary",
    "staryy": "stary",
    "nova": "novaya",
    "novyi": "novy",
    "novyy": "novy",
    "velyka": "bolshaya",
    "mala": "malaya",
    # Ordinals
    "persha": "pervaya",
    "druha": "vtoraya",
    "tretya": "tretya",
    # Colour adjectives etc.
    "krasnyi": "krasny",
    "krasnyy": "krasny",
    # Terniv→Ternov patterns
    "ternivska": "ternovskaya",
    "ternivske": "ternovskoye",
    "terniv": "ternov",
}


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def norm_name(s: str) -> str:
    """Canonicalize a place name for lookup."""
    if not s:
        return ""
    s = s.strip().lower()
    s = _strip_accents(s)
    s = " ".join(
        s.replace("\u2019", "'")
        .replace("`", "'")
        .replace("\u2013", "-")
        .split()
    )
    return s


def normalized_exonym_for_alias(exonym: str) -> str:
    """Normalize an exonym for storage in aliases."""
    if not exonym:
        return ""
    ex = exonym.lower()
    ex = ex.replace("-", " ")
    ex = ex.replace("'", "").replace("’", "")
    ex = re.sub(r"\s+", " ", ex)
    return ex.strip()


# ---------------------------------------------------------------------------
# Exonym generation utilities
# ---------------------------------------------------------------------------


def _normalize_uk_name(name: str) -> str:
    """Lowercase and collapse whitespace; keep hyphens (we need them)."""
    name = name.strip().lower()
    name = name.replace("’", "'")
    return re.sub(r"\s+", " ", name)


def uk_roman_to_ru_exonym(name: str) -> str:
    """Convert a Ukrainian romanized place name into a Russian-style exonym."""
    if not name:
        return name

    norm = _normalize_uk_name(name)

    # 1) Exact full-name mapping
    if norm in FULL_NAME_EXONYM_MAP:
        return FULL_NAME_EXONYM_MAP[norm]

    # 2) Split into tokens keeping separators
    tokens = re.split(r"([ -])", norm)
    out_tokens: list[str] = []

    for tok in tokens:
        if tok in {" ", "-"}:
            out_tokens.append(tok)
            continue

        word = tok
        mapped = WORD_EXONYM_MAP.get(word)
        if mapped:
            out_tokens.append(mapped)
            continue

        if word.endswith("ivka"):
            root = word[:-4]
            if root and (root[-1] in "bcdfghjklmnpqrstvwxyz" or root.endswith("i")):
                out_tokens.append(root + "ovka")
                continue

        if word.endswith("ivska"):
            out_tokens.append(word[:-5] + "ovskaya")
            continue
        if word.endswith("ivske"):
            out_tokens.append(word[:-5] + "ovskoye")
            continue

        out_tokens.append(word)

    return "".join(out_tokens)


_RU_TO_LATIN: Dict[str, str] = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "yo",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "kh",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "shch",
    "ы": "y",
    "э": "e",
    "ю": "yu",
    "я": "ya",
    "ь": "",
    "ъ": "",
}


def ru_to_roman(text: str) -> str:
    """Transliterate Russian Cyrillic text into a Telegram-style Latin form."""

    def _transliterate_simple(word: str) -> str:
        out: list[str] = []
        for idx, ch in enumerate(word):
            lower = ch.lower()
            mapped = _RU_TO_LATIN.get(lower)

            if mapped is None:
                out.append(ch)
                continue

            if lower == "е" and idx == 0:
                mapped = "ye"

            if ch.isupper():
                if not mapped:
                    continue
                if len(mapped) == 1:
                    out.append(mapped.upper())
                else:
                    out.append(mapped[0].upper() + mapped[1:])
            else:
                out.append(mapped)

        return "".join(out)

    def _transliterate_word(word: str) -> str:
        lower = word.lower()
        if lower.endswith("ий") or lower.endswith("ый"):
            stem = word[:-2]
            translit_stem = _transliterate_simple(stem)
            return translit_stem + "y"
        return _transliterate_simple(word)

    tokens = re.split(r"(\s+|-)", text)
    result: list[str] = []

    for tok in tokens:
        if tok == "" or tok.isspace() or tok == "-":
            result.append(tok)
            continue
        result.append(_transliterate_word(tok))

    return "".join(result)


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------


def _load_ru_exonyms_from_locales(locales_path: Path | None) -> Dict[str, str]:
    """Load wikidata->exonym mapping from a locales GeoJSON if available."""
    if locales_path is None or not locales_path.is_file():
        return {}

    with locales_path.open("r", encoding="utf-8") as fp:
        data = json.load(fp)

    mapping: Dict[str, str] = {}
    for feat in data.get("features", []):
        props = feat.get("properties", {}) or {}
        qid = (props.get("wikidata") or "").strip()
        if not qid:
            continue

        name_ru = (props.get("name:ru") or "").strip()
        if not name_ru:
            continue

        exonym = ru_to_roman(name_ru).strip()
        if exonym:
            mapping[qid] = exonym

    return mapping


def append_exonyms(
    csv_path: Path | None = None,
    locales_path: Path | None = None,
) -> None:
    """
    Append Russian exonyms and English transliterations into the aliases column
    of ``locale_lookup.csv``.

    * Adds overrides from ``FULL_NAME_EXONYM_MAP``
    * Adds transliterations of ``name:ru`` from a locales GeoJSON if provided
    * Falls back to rule-based generation via ``uk_roman_to_ru_exonym``
    * Adds English transliterations for any Cyrillic aliases already present

    Existing aliases are preserved; new ones are appended when missing after
    normalization.
    """

    csv_path = Path(csv_path) if csv_path else Path(__file__).with_name("locale_lookup.csv")

    ru_ex_by_qid = _load_ru_exonyms_from_locales(locales_path)

    rows: list[dict[str, Any]] = []
    with csv_path.open("r", encoding="utf-8", newline="") as fp:
        reader = csv.DictReader(fp)
        fieldnames = reader.fieldnames
        if not fieldnames:
            raise ValueError("CSV missing header row")
        for row in reader:
            rows.append(row)

    for row in rows:
        raw_name = (row.get("name") or "").strip()
        if not raw_name:
            continue

        norm = normalize_location_key(raw_name)
        wikidata = (row.get("wikidata") or "").strip()

        aliases_str = str(row.get("aliases") or "").strip()
        aliases_raw = [a.strip() for a in aliases_str.split(";") if a.strip()]
        normalized_existing = {normalized_exonym_for_alias(a) for a in aliases_raw}

        # Transliterate any Cyrillic aliases to English and add if missing
        for alias in list(aliases_raw):
            if re.search(r"[\u0400-\u04FF]", alias):
                translit = normalized_exonym_for_alias(ru_to_roman(alias))
                if translit and translit not in normalized_existing:
                    aliases_raw.append(translit)
                    normalized_existing.add(translit)

        exonym_candidates: list[str] = []

        full_map_val = FULL_NAME_EXONYM_MAP.get(norm)
        if full_map_val:
            exonym_candidates.extend(
                part.strip() for part in full_map_val.split(";") if part.strip()
            )

        if wikidata:
            ru_ex = ru_ex_by_qid.get(wikidata)
            if ru_ex:
                exonym_candidates.append(ru_ex)

        if not exonym_candidates:
            raw_exonym = uk_roman_to_ru_exonym(norm)
            if raw_exonym:
                exonym_candidates.extend(
                    part.strip() for part in raw_exonym.split(";") if part.strip()
                )

        for part in exonym_candidates:
            norm_ex = normalized_exonym_for_alias(part)
            if norm_ex and norm_ex not in normalized_existing:
                aliases_raw.append(norm_ex)
                normalized_existing.add(norm_ex)

        row["aliases"] = ";".join(aliases_raw)

    with csv_path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\N{CHECK MARK} Added exonyms to: {csv_path}")


if __name__ == "__main__":
    append_exonyms()
