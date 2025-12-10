def extract_post_contexts(post: Post, doc: Doc):
    """
    Minimal deterministic detection of preposed post-wide context.
    """

    ents = doc.ents
    seen_context = False

    for ent in ents:
        if ent.start > 12:
            # heuristic: context phrases always come early
            break

        if ent.label_ in {"REGION", "GROUP", "DIRECTION"}:
            ctx = SitRepContext(
                kind=_ctx_kind_for_label(ent.label_),
                text=ent.text,
                value=ent.text,
                post_id=post.post_id,
            )
            post.contexts.append(ctx)
            seen_context = True

    return post.contexts


def extract_section_contexts(section: Section, doc: Doc):
    """
    Extracts section-wide context using same rules as post,
    but scoped to the doc span corresponding to the section's text.
    """

    text = section.text
    start = doc.text.find(text)
    end = start + len(text)
    span = doc.char_span(start, end)

    if span is None:
        return

    ents = [ent for ent in doc.ents if ent.start_char >= start and ent.end_char <= end]

    for ent in ents:
        if ent.start_char - start > 40:
            break  # context appears near the start of the section

        if ent.label_ in {"REGION", "GROUP", "DIRECTION"}:
            section.contexts.append(
                SitRepContext(
                    kind=_ctx_kind_for_label(ent.label_),
                    text=ent.text,
                    value=ent.text,
                    section_id=section.section_id,
                )
            )
