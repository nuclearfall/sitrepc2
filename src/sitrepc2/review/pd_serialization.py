# src/sitrepc2/review/pd_serialization.py

from __future__ import annotations
import json
from typing import Dict, Any, Type

from sitrepc2.review.pd_nodes import (
    ReviewNode, PDPost, PDSection, PDEvent, PDLocation
)
from sitrepc2.util.serialization import serialize, deserialize


# ---------------------------------------------------------------------------
# NODE → DICT
# ---------------------------------------------------------------------------

def pd_node_to_dict(node: ReviewNode) -> Dict[str, Any]:
    """
    Convert any PD node (and subtree) to a JSON-serializable dict.
    Uses the project's generic dataclass serializer for all fields.

    The only custom handling is: children and type name.
    """
    d = serialize(node)  # serialize all dataclass fields recursively
    d["__type__"] = node.__class__.__name__
    d["children"] = [pd_node_to_dict(ch) for ch in node.children]
    return d


# ---------------------------------------------------------------------------
# DICT → NODE
# ---------------------------------------------------------------------------

TYPE_MAP: Dict[str, Type[ReviewNode]] = {
    "PDPost": PDPost,
    "PDSection": PDSection,
    "PDEvent": PDEvent,
    "PDLocation": PDLocation,
}


def pd_node_from_dict(data: Dict[str, Any], parent=None) -> ReviewNode:
    """
    Reconstruct a PD node dataclass recursively.
    This uses util.deserialize() for dataclass fields, and manually
    attaches children & parent links.
    """

    clsname = data.pop("__type__", None)
    if clsname not in TYPE_MAP:
        raise ValueError(f"Unknown PD node type in JSON: {clsname}")

    cls = TYPE_MAP[clsname]

    # Extract children; the rest goes into the dataclass
    children_data = data.pop("children", [])

    # Rebuild dataclass fields
    node = deserialize(data, cls)
    node.parent = parent
    node.children = []

    # Rebuild children recursively
    for ch in children_data:
        child = pd_node_from_dict(ch, parent=node)
        node.children.append(child)

    return node


# ---------------------------------------------------------------------------
# JSON convenience wrappers
# ---------------------------------------------------------------------------

def pd_tree_to_json(root: PDPost) -> str:
    return json.dumps(pd_node_to_dict(root), ensure_ascii=False, indent=2)


def pd_tree_from_json(s: str) -> PDPost:
    data = json.loads(s)
    return pd_node_from_dict(data)
