# src/sitrepc2/review/pd_writer.py

from __future__ import annotations
import json
import csv
from pathlib import Path
from typing import Iterable, Dict, Any

from sitrepc2.review.pd_nodes import (
    PDPost, PDSection, PDEvent, PDLocation, ReviewNode
)


# ============================================================
# HELPERS
# ============================================================

def _node_to_dict(node: ReviewNode) -> Dict[str, Any]:
    """
    Convert a PD node (recursively) to a JSON-serializable dict.
    """
    base = {
        "type": node.__class__.__name__,
        "summary": node.summary,
        "snippet": node.snippet,
        "contexts": [c.to_json() for c in node.contexts],
        "enabled": node.enabled,
        "children": []
    }

    # Post
    if isinstance(node, PDPost):
        base["post_id"] = node.post_id
        base["raw_text"] = node.raw_text

    # Section
    elif isinstance(node, PDSection):
        base["section_id"] = node.section_id
        base["raw_text"] = node.raw_text

    # Event
    elif isinstance(node, PDEvent):
        base["event_id"] = node.event_id
        base["raw_text"] = node.raw_text
        base["actor"] = {
            "kind": node.actor_kind,
            "text": node.actor_text,
        }
        base["action"] = {
            "kind": node.action_kind,
            "text": node.action_text,
        }
        if node.cluster_diagnostics:
            base["diagnostics"] = node.cluster_diagnostics.__dict__

    # Location
    elif isinstance(node, PDLocation):
        base["location_id"] = node.location_id
        base["raw_text"] = node.raw_text
        base["span_text"] = node.span_text
        base["candidate_texts"] = node.candidate_texts

        if node.final_locale:
            base["final_locale"] = {
                "name": node.final_locale.name,
                "lat": node.final_locale.lat,
                "lon": node.final_locale.lon,
                "region": node.final_locale.region,
                "ru_group": node.final_locale.ru_group,
            }
            base["final_confidence"] = node.final_confidence

    for child in node.children:
        base["children"].append(_node_to_dict(child))

    return base


# ============================================================
# JSON EXPORT
# ============================================================

def export_tree_to_json(root: ReviewNode, path: Path) -> None:
    d = _node_to_dict(root)
    with path.open("w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)


# ============================================================
# CSV EXPORT (EVENTS OR LOCATIONS)
# ============================================================

def export_events_to_csv(posts: Iterable[PDPost], path: Path) -> None:
    """
    Flatten the DOM output: one row per event.
    """
    rows = []
    for post in posts:
        for sec in post.children:
            for ev in sec.children:
                actor = ev.actor_text or ""
                action = ev.action_text or ""

                rows.append({
                    "post_id": post.post_id,
                    "section_id": sec.section_id,
                    "event_id": ev.event_id,
                    "actor": actor,
                    "action": action,
                    "contexts": "; ".join(c.text for c in ev.contexts),
                })

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def export_locations_to_csv(posts: Iterable[PDPost], path: Path) -> None:
    """
    Flatten the DOM output: one row per resolved location.
    """
    rows = []
    for post in posts:
        for sec in post.children:
            for ev in sec.children:
                for loc in ev.children:
                    if isinstance(loc, PDLocation) and loc.final_locale:
                        rows.append({
                            "post_id": post.post_id,
                            "section_id": sec.section_id,
                            "event_id": ev.event_id,
                            "location_id": loc.location_id,
                            "span_text": loc.span_text,
                            "resolved_name": loc.final_locale.name,
                            "lat": loc.final_locale.lat,
                            "lon": loc.final_locale.lon,
                            "confidence": loc.final_confidence,
                        })

    if not rows:
        return

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


# ============================================================
# KML EXPORT
# ============================================================

def export_locations_to_kml(posts: Iterable[PDPost], path: Path) -> None:
    """
    Minimal KML export of all resolved locations.
    """
    placemarks = []

    for post in posts:
        for sec in post.children:
            for ev in sec.children:
                for loc in ev.children:
                    if isinstance(loc, PDLocation) and loc.final_locale:
                        name = loc.final_locale.name
                        lat = loc.final_locale.lat
                        lon = loc.final_locale.lon
                        event_desc = f"Post {post.post_id}, Event {ev.event_id}"

                        placemarks.append(f"""
        <Placemark>
            <name>{name}</name>
            <description>{event_desc}</description>
            <Point>
                <coordinates>{lon},{lat},0</coordinates>
            </Point>
        </Placemark>
        """)

    kml = f"""
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
    {''.join(placemarks)}
</Document>
</kml>
"""

    with path.open("w", encoding="utf-8") as f:
        f.write(kml.strip())
