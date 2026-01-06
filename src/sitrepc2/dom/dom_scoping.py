from __future__ import annotations

import sqlite3
from typing import Dict, Iterable, List, Set

from sitrepc2.lss.lss_scoping import LSSContextHint
from sitrepc2.config.paths import gazetteer_path


# ============================================================
# Context dominance
# ============================================================

DOM_CONTEXT_ORDER = ("LOCATION", "SERIES", "EVENT", "SECTION", "POST")


def _collect_context_chain(
    *,
    dom_snapshot_id: int,
    node_id: int,
    dom_conn: sqlite3.Connection,
    context_hints: Iterable[LSSContextHint],
) -> Dict[str, Set[int]]:
    """
    Resolve effective context for a DOM node by dominance order.
    Snapshot-local and deterministic.
    """

    cur = dom_conn.cursor()

    cur.execute(
        """
        WITH RECURSIVE ancestors(id, node_type, parent_id) AS (
            SELECT dn.id, dn.node_type, dn.parent_id
            FROM dom_node dn
            JOIN dom_node_state st
              ON st.dom_node_id = dn.id
             AND st.dom_snapshot_id = ?
            WHERE dn.id = ?

            UNION ALL

            SELECT parent.id, parent.node_type, parent.parent_id
            FROM dom_node parent
            JOIN ancestors a ON parent.id = a.parent_id
        )
        SELECT id, node_type
        FROM ancestors
        """,
        (dom_snapshot_id, node_id),
    )

    nodes = cur.fetchall()
    node_ids_by_type = {nt: nid for nid, nt in nodes}

    resolved: Dict[str, Set[int]] = {}

    for scope in DOM_CONTEXT_ORDER:
        for hint in context_hints:
            if hint.scope != scope:
                continue

            target_ok = (
                hint.target_id is None
                or node_ids_by_type.get(scope) == hint.target_id
            )

            if not target_ok:
                continue

            resolved.setdefault(hint.ctx_kind, set()).add(hint.target_id)

    return resolved


# ============================================================
# Gazetteer filtering
# ============================================================

def _filter_location_candidates(
    *,
    location_text: str,
    context: Dict[str, Set[int]],
    gaz_conn: sqlite3.Connection,
) -> List[int]:
    """
    Filter gazetteer location candidates using REGION / GROUP context.
    """

    cur = gaz_conn.cursor()
    norm = location_text.strip().lower()

    cur.execute(
        """
        SELECT location_id
        FROM location_aliases
        WHERE normalized = ?
        """,
        (norm,),
    )

    candidates = {row[0] for row in cur.fetchall()}
    if not candidates:
        return []

    if "REGION" in context and context["REGION"]:
        region_ids = context["REGION"]
        cur.execute(
            f"""
            SELECT location_id
            FROM location_regions
            WHERE region_id IN ({",".join("?" * len(region_ids))})
            """,
            tuple(region_ids),
        )
        candidates &= {row[0] for row in cur.fetchall()}

    if "GROUP" in context and context["GROUP"]:
        group_ids = context["GROUP"]
        cur.execute(
            f"""
            SELECT location_id
            FROM location_groups
            WHERE group_id IN ({",".join("?" * len(group_ids))})
            """,
            tuple(group_ids),
        )
        candidates &= {row[0] for row in cur.fetchall()}

    return sorted(candidates)


# ============================================================
# Public API
# ============================================================

def scope_dom_locations(
    *,
    dom_conn: sqlite3.Connection,
    dom_snapshot_id: int,
    context_hints: Iterable[LSSContextHint],
) -> None:
    """
    Attach filtered LocationCandidates to DOM LOCATION nodes.
    Snapshot-local and idempotent.
    """

    gaz_conn = sqlite3.connect(gazetteer_path())
    dom_cur = dom_conn.cursor()
    gaz_cur = gaz_conn.cursor()

    # Fetch LOCATION nodes with their LSS event provenance
    dom_cur.execute(
        """
        SELECT dn.id, dp.lss_event_id
        FROM dom_node dn
        JOIN dom_node_state st
          ON st.dom_node_id = dn.id
         AND st.dom_snapshot_id = ?
        JOIN dom_node_provenance dp
          ON dp.dom_node_id = dn.id
        WHERE dn.node_type = 'LOCATION'
          AND st.deduped = FALSE
        """,
        (dom_snapshot_id,),
    )

    for dom_loc_id, lss_event_id in dom_cur.fetchall():
        if lss_event_id is None:
            continue

        # Retrieve location texts from LSS
        dom_cur.execute(
            """
            SELECT li.text
            FROM lss_location_items li
            JOIN lss_location_series ls
              ON ls.id = li.series_id
            WHERE ls.lss_event_id = ?
            ORDER BY li.ordinal
            """,
            (lss_event_id,),
        )

        location_texts = [row[0] for row in dom_cur.fetchall()]

        if not location_texts:
            continue

        context = _collect_context_chain(
            dom_snapshot_id=dom_snapshot_id,
            node_id=dom_loc_id,
            dom_conn=dom_conn,
            context_hints=context_hints,
        )

        for location_text in location_texts:
            candidate_ids = _filter_location_candidates(
                location_text=location_text,
                context=context,
                gaz_conn=gaz_conn,
            )

            for loc_id in candidate_ids:
                dom_cur.execute(
                    """
                    SELECT 1
                    FROM dom_location_candidate
                    WHERE dom_snapshot_id = ?
                      AND location_node_id = ?
                      AND gazetteer_location_id = ?
                    """,
                    (dom_snapshot_id, dom_loc_id, loc_id),
                )
                if dom_cur.fetchone():
                    continue

                gaz_cur.execute(
                    """
                    SELECT lat, lon, name, place, wikidata
                    FROM locations
                    WHERE location_id = ?
                    """,
                    (loc_id,),
                )
                row = gaz_cur.fetchone()
                if row is None:
                    continue

                lat, lon, name, place, wikidata = row

                dom_cur.execute(
                    """
                    INSERT INTO dom_location_candidate (
                        dom_snapshot_id,
                        location_node_id,
                        gazetteer_location_id,
                        lat,
                        lon,
                        name,
                        place,
                        wikidata,
                        confidence,
                        dist_from_front,
                        selected,
                        persists
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, FALSE, FALSE)
                    """,
                    (
                        dom_snapshot_id,
                        dom_loc_id,
                        loc_id,
                        lat,
                        lon,
                        name,
                        place,
                        wikidata,
                    ),
                )

    dom_conn.commit()
    gaz_conn.close()
