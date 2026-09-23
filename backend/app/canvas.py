"""The shape a saved map must have. The canvas is React Flow JSON written by the browser, so the
server checks it before saving or reasoning over it: every node has a unique id and a position,
parents exist and never loop, and the map stays within a size a person could draw. Extra fields
React Flow adds (measured sizes, styles, z-order) pass through untouched."""
import json
import math

from fastapi import HTTPException

MAX_NODES = 2000
MAX_EDGES = 5000
MAX_BYTES = 5_000_000
MAX_ID = 100


class MapDataError(HTTPException):
    def __init__(self, why: str):
        super().__init__(422, f"The map data was incomplete, so it wasn't used ({why}). Reload the page and try again.")
        self.why = why


def _bad(why: str) -> MapDataError:
    return MapDataError(why)


def _num(v) -> bool:
    return isinstance(v, int | float) and not isinstance(v, bool) and math.isfinite(v)


def validate_doc(doc: dict) -> dict:
    """Returns the map with edges to missing elements dropped; raises 422 for anything else wrong."""
    if not isinstance(doc, dict):
        raise _bad("not a map")
    nodes, edges = doc.get("nodes"), doc.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise _bad("no elements or connections")
    if len(nodes) > MAX_NODES or len(edges) > MAX_EDGES:
        raise _bad(f"more than {MAX_NODES} elements or {MAX_EDGES} connections")
    if len(json.dumps(doc, default=str)) > MAX_BYTES:
        raise _bad("too large")
    ids: set[str] = set()
    parents: dict[str, str] = {}
    for n in nodes:
        if not isinstance(n, dict):
            raise _bad("an element isn't an object")
        nid = n.get("id")
        if not isinstance(nid, str) or not nid or len(nid) > MAX_ID:
            raise _bad("an element has no id")
        if nid in ids:
            raise _bad(f"two elements share the id {nid[:40]}")
        ids.add(nid)
        if not isinstance(n.get("type", ""), str):
            raise _bad("an element has an unknown type")
        pos = n.get("position")
        if not isinstance(pos, dict) or not _num(pos.get("x")) or not _num(pos.get("y")):
            raise _bad("an element has no position")
        if n.get("data") is not None and not isinstance(n["data"], dict):
            raise _bad("an element's details aren't an object")
        if n.get("parentId"):
            if not isinstance(n["parentId"], str):
                raise _bad("an element has an unreadable parent")
            parents[nid] = n["parentId"]
    for child, parent in parents.items():
        if parent not in ids:
            raise _bad("an element sits inside one that doesn't exist")
        seen = {child}
        while parent in parents:
            if parent in seen:
                raise _bad("elements sit inside each other in a loop")
            seen.add(parent)
            parent = parents[parent]
    kept = []
    for e in edges:
        if not isinstance(e, dict) or not isinstance(e.get("id", ""), str):
            raise _bad("a connection isn't an object")
        if e.get("data") is not None and not isinstance(e["data"], dict):
            raise _bad("a connection's details aren't an object")
        if e.get("source") in ids and e.get("target") in ids:
            kept.append(e)
    return {**doc, "edges": kept}
