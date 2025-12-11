# sitrepc2/nlp/sectioning.py

import re
from typing import List
from spacy.tokens import Doc
from sitrepc2.lss.typedefs import Section, SitRepContext, CtxKind

SECTION_HEADING_RE = re.compile(
    r"^\s*(?:[-•*]|#+|\*)\s*[A-ZА-ЯЁІЇЄҐ][^:]{2,}:?$"
)

def split_into_sections(post_text: str, doc: Doc) -> List[Section]:
    """
    Deterministic section splitter.
    Uses:
        • entity-ruler detected DIRECTION/GROUP/REGION at line start
        • formatting cues
        • fallback multi-paragraph splitting
    """

    lines = post_text.split("\n")
    sections: List[Section] = []

    current_lines = []
    current_id = 0

    def flush_section():
        nonlocal current_id, current_lines
        if not current_lines:
            return
        text = "\n".join(current_lines).strip()
        section = Section(section_id=f"S{current_id}", text=text)
        sections.append(section)
        current_id += 1
        current_lines = []

    # Pass 1: split by headings & entity cues
    for i, line in enumerate(lines):
        stripped = line.strip()

        # Heading-style boundaries
        if SECTION_HEADING_RE.match(stripped):
            flush_section()
            current_lines.append(line)
            continue

        # Entity-based boundaries
        ents = [ent for ent in doc.ents if ent.start_char >= doc.char_span(i) and ent.start_char < doc.char_span(i+1)]
        if any(ent.label_ in {"DIRECTION", "GROUP", "REGION"} for ent in ents):
            flush_section()
            current_lines.append(line)
            continue

        current_lines.append(line)

    flush_section()

    # Pass 2: Fallback — split long freeform text
    final_sections = []
    for section in sections:
        if len(section.text) > 800 and "\n\n" in section.text:
            paragraphs = section.text.split("\n\n")
            for idx, p in enumerate(paragraphs):
                final_sections.append(
                    Section(section_id=f"{section.section_id}.{idx}", text=p.strip())
                )
        else:
            final_sections.append(section)

    return final_sections
