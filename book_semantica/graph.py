"""Graph build, duplicate detection, and conflict detection."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from book_semantica.provenance import stamp_entity
from book_semantica.quality import collect_duplicates, filter_conflicts


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return _jsonable(value.value)
    if is_dataclass(value) and not isinstance(value, type):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    return str(value)


def _entity_keys(entity: dict) -> list[str]:
    keys = []
    for field in ("id", "entity_id", "name", "text"):
        value = entity.get(field)
        if value:
            keys.append(str(value))
    return keys


def restore_entity_provenance(
    graph: dict, pre_entities: list[dict], book_key: str
) -> dict:
    """Copy book_key and page onto merged nodes from the pre-merge entities."""
    buckets: dict[str, list[dict]] = {}
    for entity in pre_entities:
        for key in _entity_keys(entity):
            buckets.setdefault(key, []).append(entity)

    for entity in graph.get("entities") or []:
        sources: list[dict] = []
        for key in _entity_keys(entity):
            sources.extend(buckets.get(key) or [])
        pages = []
        for src in sources:
            page = src.get("page")
            if page is None:
                page = (src.get("metadata") or {}).get("page")
            if page is not None:
                pages.append(page)
        keys = []
        for src in sources:
            stamped = src.get("book_key") or (src.get("metadata") or {}).get("book_key")
            if stamped:
                keys.append(stamped)
        page = pages[0] if pages else entity.get("page")
        if page is None:
            page = (entity.get("metadata") or {}).get("page")
        chosen_key = keys[0] if keys else book_key
        stamped = stamp_entity(entity, book_key=chosen_key, page=page)
        entity.clear()
        entity.update(stamped)
    return graph


def build_graph(entities: list[dict], relationships: list[dict]) -> dict[str, Any]:
    from semantica.kg import GraphBuilder

    builder = GraphBuilder(merge_entities=True, resolve_conflicts=True)
    return builder.build(
        {"entities": entities, "relationships": relationships},
        extract=False,
        extract_relations=False,
        extract_triplets=False,
    )


def detect_duplicates(
    entities: list[dict], relationships: list[dict] | None = None
) -> dict[str, Any]:
    result = collect_duplicates(entities, relationships)
    try:
        from semantica.deduplication import DuplicateDetector

        detector = DuplicateDetector(similarity_threshold=0.85, use_clustering=False)
        extra = detector.detect_duplicates(entities)
        if extra:
            result["detector_candidates"] = _jsonable(extra)
    except Exception as exc:
        result["detector_error"] = str(exc)
    return result


def detect_conflicts(entities: list[dict], relationships: list[dict]) -> list[dict]:
    """Run Semantica ConflictDetector.value on definition/type/comment.

    method="all" often returns nothing unless conflict_fields is set.
    Value conflicts fire when two entities share an id and disagree on a property.
    """
    from semantica.conflicts import ConflictDetector

    detector = ConflictDetector()
    found: list[Any] = []
    for prop in ("definition", "type", "comment"):
        try:
            found.extend(
                detector.detect_conflicts(
                    entities, method="value", property_name=prop
                )
                or []
            )
        except Exception:
            continue
    try:
        found.extend(detector.detect_relationship_conflicts(relationships) or [])
    except Exception:
        pass
    return filter_conflicts(_jsonable(found))
