from __future__ import annotations

import sqlite3
from typing import Dict, Iterable, List, Optional, Set

from sitrepc2.lss.lss_scoping import LSSContextHint
from sitrepc2.config.paths import gazetteer_path


# ============================================================
# Context dominance
# ============================================================

DOM_CONTEXT_ORDER = ("LOCATION", "SERIES", "EVENT", "SECTION", "POST")


def _collect_context_chain(
    *,
    node_id: int,
    node_type: str,
    dom_conn: sqlite3.Connection,
    context_hints: Iterable[LSSContextHint],
) -> Dict[str, Set[int]]:
    """
    Resolve effective context for a DOM node by dominance order.

    Returns:
        ctx_kind -> set(entity_ids)
    """

    cur = dom_conn.cursor()

    # Walk ancestors bottom-up
    cur.execute(
        """
        WITH RECURSIVE ancestors(id, node_type, parent_id) AS (
            SELECT id, node_type, parent_id
            FROM dom_node
            WHERE id = ?

            UNION ALL

            SELECT n.id, n.node_type, n.parent_id
            FROM dom_node n
            JOIN ancestors a ON n.id = a.parent_id
        )
        SELECT id, node_type
        FROM ancestors
        """,
        (node_id,),
    )

    nodes = cur.fetchall()
    node_ids_by_type = {nt: i for i, nt in nodes}

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

    Returns:
        list of location_id
    """

    cur = gaz_conn.cursor()

    norm = location_text.strip().lower()

    # ------------------------------------------------------------
    # Alias match
    # ------------------------------------------------------------

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

    # ------------------------------------------------------------
    # Region constraint
    # ------------------------------------------------------------

    if "REGION" in context:
        region_ids = context["REGION"]

        cur.execute(
            """
            SELECT location_id
            FROM location_regions
            WHERE region_id IN ({})
            """.format(",".join("?" * len(region_ids))),
            tuple(region_ids),
        )

        allowed = {row[0] for row in cur.fetchall()}
        candidates &= allowed

    # ------------------------------------------------------------
    # Group constraint
    # ------------------------------------------------------------

    if "GROUP" in context:
        group_ids = context["GROUP"]

        cur.execute(
            """
            SELECT location_id
            FROM location_groups
            WHERE group_id IN ({})
            """.format(",".join("?" * len(group_ids))),
            tuple(group_ids),
        )

        allowed = {row[0] for row in cur.fetchall()}
        candidates &= allowed

    return sorted(candidates)


# ============================================================
# Public API
# ============================================================

def scope_dom_locations(
    *,
    dom_conn: sqlite3.Connection,
    context_hints: Iterable[LSSContextHint],
) -> None:
    """
    Attach filtered LocationCandidates to DOM LOCATION nodes.

    Effects:
      • Inserts rows into dom_location_candidate
      • Does NOT mark resolved
      • Does NOT select a candidate
    """

    gaz_conn = sqlite3.connect(gazetteer_path())
    dom_cur = dom_conn.cursor()

    dom_cur.execute(
        """
        SELECT id
        FROM dom_node
        WHERE node_type = 'LOCATION'
        """
    )

    location_nodes = [row[0] for row in dom_cur.fetchall()]

    for dom_loc_id in location_nodes:
        dom_cur.execute(
            """
            SELECT dn.id, dp.text
            FROM dom_node dn
            JOIN dom_node_provenance dp ON dp.dom_node_id = dn.id
            WHERE dn.id = ?
            """,
            (dom_loc_id,),
        )

        row = dom_cur.fetchone()
        if row is None:
            continue

        _, location_text = row

        context = _collect_context_chain(
            node_id=dom_loc_id,
            node_type="LOCATION",
            dom_conn=dom_conn,
            context_hints=context_hints,
        )

        candidates = _filter_location_candidates(
            location_text=location_text,
            context=context,
            gaz_conn=gaz_conn,
        )

        for loc_id in candidates:
            dom_cur.execute(
                """
                INSERT INTO dom_location_candidate (
                    dom_node_id,
                    location_id,
                    selected
                )
                VALUES (?, ?, FALSE)
                """,
                (dom_loc_id, loc_id),
            )

    dom_conn.commit()
    gaz_conn.close()
