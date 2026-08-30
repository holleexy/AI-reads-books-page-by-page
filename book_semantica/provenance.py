"""Stamp book_key (required) and page (when present) onto graph items."""

from __future__ import annotations

from typing import Any


def stamp_entity(entity: dict, book_key: str, page: int | None = None) -> dict:
    out = dict(entity)
    meta = dict(out.get("metadata") or {})
    out["book_key"] = book_key
    meta["book_key"] = book_key
    if page is not None:
        out["page"] = page
        meta["page"] = page
    else:
        out.pop("page", None)
        meta.pop("page", None)
    out["metadata"] = meta
    return out


def stamp_relation(relation: dict, book_key: str, page: int | None = None) -> dict:
    out = dict(relation)
    meta = dict(out.get("metadata") or {})
    out["book_key"] = book_key
    meta["book_key"] = book_key
    if page is not None:
        out["page"] = page
        meta["page"] = page
    else:
        out.pop("page", None)
        meta.pop("page", None)
    out["metadata"] = meta
    return out


def record_entities(entities: list[dict], book_key: str, storage=None) -> Any:
    """Record provenance via Semantica when the package is importable."""
    from semantica.provenance import InMemoryStorage, ProvenanceManager

    if storage is None:
        storage = InMemoryStorage()
    manager = ProvenanceManager(storage=storage)
    for entity in entities:
        entity_id = str(
            entity.get("id")
            or entity.get("entity_id")
            or entity.get("name")
            or entity.get("text")
            or ""
        )
        if not entity_id:
            continue
        metadata = dict(entity.get("metadata") or {})
        if entity.get("page") is not None:
            metadata.setdefault("page", entity["page"])
        metadata.setdefault("book_key", entity.get("book_key") or book_key)
        manager.track_entity(
            entity_id=entity_id,
            source=book_key,
            metadata=metadata,
        )
    return manager
