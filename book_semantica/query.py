"""Look up neighbors and shortest paths on a book graph dict."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any


def entity_name(entity: dict) -> str:
    return str(
        entity.get("name")
        or entity.get("text")
        or entity.get("label")
        or entity.get("id")
        or ""
    )


def entity_id(entity: dict) -> str:
    return str(
        entity.get("id")
        or entity.get("entity_id")
        or entity_name(entity)
    )


def index_graph(graph: dict) -> tuple[dict[str, dict], dict[str, str], dict[str, list]]:
    by_id: dict[str, dict] = {}
    name_to_id: dict[str, str] = {}
    adjacency: dict[str, list] = defaultdict(list)
    for entity in graph.get("entities") or []:
        eid = entity_id(entity)
        by_id[eid] = entity
        name_to_id[eid] = eid
        name = entity_name(entity)
        if name:
            name_to_id[name] = eid
    for rel in graph.get("relationships") or []:
        src = rel.get("source") or rel.get("subject")
        tgt = rel.get("target") or rel.get("object")
        if not src or not tgt:
            continue
        src = str(src)
        tgt = str(tgt)
        adjacency[src].append((tgt, rel))
        adjacency[tgt].append((src, rel))
    return by_id, name_to_id, adjacency


def resolve_name(graph: dict, name: str) -> str | None:
    _by_id, name_to_id, _adj = index_graph(graph)
    if name in name_to_id:
        return name_to_id[name]
    lowered = name.lower()
    for key, eid in name_to_id.items():
        if key.lower() == lowered:
            return eid
    for key, eid in name_to_id.items():
        if name in key or key in name:
            return eid
    return None


def neighbors(graph: dict, name: str) -> dict[str, Any]:
    by_id, _name_to_id, adjacency = index_graph(graph)
    nid = resolve_name(graph, name)
    if nid is None:
        return {"name": name, "id": None, "neighbors": []}
    found = []
    seen = set()
    for other_id, rel in adjacency.get(nid, []):
        key = (other_id, rel.get("type") or rel.get("predicate"))
        if key in seen:
            continue
        seen.add(key)
        other = by_id.get(other_id, {"id": other_id, "name": other_id})
        found.append(
            {
                "id": other_id,
                "name": entity_name(other) or other_id,
                "relation": rel.get("type") or rel.get("predicate"),
                "direction": "out"
                if str(rel.get("source") or rel.get("subject")) == nid
                else "in",
            }
        )
    return {
        "name": entity_name(by_id.get(nid, {"name": name})) or name,
        "id": nid,
        "neighbors": found,
    }


def shortest_path(graph: dict, source: str, target: str) -> dict[str, Any]:
    by_id, _name_to_id, adjacency = index_graph(graph)
    src = resolve_name(graph, source)
    tgt = resolve_name(graph, target)
    if src is None or tgt is None:
        return {"nodes": [], "source": source, "target": target, "found": False}
    if src == tgt:
        return {"nodes": [src], "source": source, "target": target, "found": True}
    queue = deque([src])
    prev: dict[str, str | None] = {src: None}
    while queue:
        current = queue.popleft()
        for other_id, _rel in adjacency.get(current, []):
            if other_id in prev:
                continue
            prev[other_id] = current
            if other_id == tgt:
                queue.clear()
                break
            queue.append(other_id)
    if tgt not in prev:
        return {"nodes": [], "source": source, "target": target, "found": False}
    nodes = [tgt]
    while prev[nodes[-1]] is not None:
        nodes.append(prev[nodes[-1]])  # type: ignore[arg-type]
    nodes.reverse()
    return {
        "nodes": nodes,
        "names": [entity_name(by_id.get(n, {"name": n})) or n for n in nodes],
        "source": source,
        "target": target,
        "found": True,
    }
