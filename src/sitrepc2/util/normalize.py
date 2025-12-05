import re
from pathlib import Path

def normalize_location_key(name: str) -> str:
    """
    Normalize a location name into a canonical key for matching.

    Rules:
      - lowercase
      - remove apostrophes: "boromels'ke" → "boromelske"
      - turn hyphens/dashes into spaces: "yeni-kale" → "yeni kale"
      - collapse multiple spaces
      - strip leading/trailing spaces
    """
    if isinstance(name, Path):
        name = str(name)
    if not name:
        return ""

    s = name.lower()

    # Remove apostrophes (both straight and common curly ones if you like)
    s = s.replace("'", "").replace("’", "").replace("the", "")

    # Treat hyphens/dashes as word separators
    for dash in ("-", "–", "—"):
        s = s.replace(dash, " ")

    # Collapse whitespace
    s = re.sub(r"\s+", " ", s)

    return s.strip()

def normalize_text(text: str) -> str:
    """
    Normalize text for matching:
      - lowercase
      - replace apostrophes (both ASCII ' and Unicode variations) with nothing
      - replace hyphens with spaces
    """
    if not text:
        return ""

    # Normalize apostrophes
    apostrophes = ["'", "’", "‘", "ʼ"]
    for a in apostrophes:
        text = text.replace(a, "")

    # Hyphens to spaces (includes Unicode non-breaking hyphens if needed)
    hyphens = ["-", "-", "‒", "–", "—"]  # common hyphen/dash variants
    for h in hyphens:
        text = text.replace(h, " ")

    return text.lower()
