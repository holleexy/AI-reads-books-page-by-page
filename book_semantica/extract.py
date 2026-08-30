"""LLM NER and relation extraction over knowledge points.

Calls Semantica's llm methods directly. Does not use NamedEntityRecognizer
or RelationExtractor, because those fall back to English pattern NER.
"""

from __future__ import annotations

from typing import Any

from book_semantica.paths import DEFAULT_MODEL
from book_semantica.provenance import stamp_entity, stamp_relation
from book_semantica.xai_provider import register_xai_provider


class LLMExtractionError(RuntimeError):
    """xAI / LLM extraction failed. Pattern NER was not used."""


def _entity_to_dict(entity: Any, book_key: str, page: int | None) -> dict:
    if isinstance(entity, dict):
        payload = dict(entity)
        if "text" in payload and "name" not in payload:
            payload["name"] = payload["text"]
        if "label" in payload and "type" not in payload:
            payload["type"] = payload["label"]
        if "id" not in payload and "entity_id" not in payload:
            payload["id"] = payload.get("name") or payload.get("text")
        return stamp_entity(payload, book_key=book_key, page=page)

    text = getattr(entity, "text", None) or getattr(entity, "name", None) or str(entity)
    label = getattr(entity, "label", None) or getattr(entity, "type", "UNKNOWN")
    payload = {
        "id": text,
        "name": text,
        "text": text,
        "type": label,
        "confidence": getattr(entity, "confidence", 1.0),
        "metadata": dict(getattr(entity, "metadata", None) or {}),
    }
    return stamp_entity(payload, book_key=book_key, page=page)


def _relation_to_dict(relation: Any, book_key: str, page: int | None) -> dict:
    if isinstance(relation, dict):
        payload = dict(relation)
        if "subject" in payload and "source" not in payload:
            src = payload["subject"]
            payload["source"] = getattr(src, "text", None) or getattr(src, "id", None) or src
        if "object" in payload and "target" not in payload:
            tgt = payload["object"]
            payload["target"] = getattr(tgt, "text", None) or getattr(tgt, "id", None) or tgt
        if "predicate" in payload and "type" not in payload:
            payload["type"] = payload["predicate"]
        payload["source"] = str(payload.get("source") or "")
        payload["target"] = str(payload.get("target") or "")
        return stamp_relation(payload, book_key=book_key, page=page)

    subject = getattr(relation, "subject", None)
    obj = getattr(relation, "object", None)
    subj_id = (
        getattr(subject, "text", None)
        or getattr(subject, "id", None)
        or str(subject)
    )
    obj_id = getattr(obj, "text", None) or getattr(obj, "id", None) or str(obj)
    payload = {
        "source": str(subj_id),
        "target": str(obj_id),
        "type": getattr(relation, "predicate", None) or "related_to",
        "confidence": getattr(relation, "confidence", 1.0),
        "metadata": dict(getattr(relation, "metadata", None) or {}),
    }
    return stamp_relation(payload, book_key=book_key, page=page)


def _reject_pattern_entities(entities: list) -> None:
    for entity in entities or []:
        meta = getattr(entity, "metadata", None)
        if isinstance(entity, dict):
            meta = entity.get("metadata") or {}
        method = (meta or {}).get("extraction_method")
        if method in {"pattern", "last_resort_pattern"}:
            raise LLMExtractionError(
                "refusing English pattern NER result; LLM extraction did not run"
            )


def extract_entities_relations(
    items: list[dict], config
) -> tuple[list[dict], list[dict], dict[str, str]]:
    register_xai_provider()
    from semantica.semantic_extract.methods import (
        get_entity_method,
        get_relation_method,
    )

    model = getattr(config, "model", None) or DEFAULT_MODEL
    book_key = getattr(config, "book_key")
    extract_ents = get_entity_method("llm")
    extract_rels = get_relation_method("llm")
    entities: list[dict] = []
    relations: list[dict] = []
    for item in items:
        text = item.get("text") or ""
        if not text.strip():
            continue
        page = item.get("page")
        try:
            extracted = extract_ents(
                text,
                provider="xai",
                llm_model=model,
                model=model,
                silent_fail=False,
            )
        except Exception as exc:
            raise LLMExtractionError(f"LLM NER failed: {exc}") from exc
        _reject_pattern_entities(extracted)
        entities.extend(_entity_to_dict(ent, book_key, page) for ent in extracted or [])
        if not extracted:
            continue
        try:
            extracted_rels = extract_rels(
                text,
                extracted,
                provider="xai",
                llm_model=model,
                model=model,
                silent_fail=False,
            )
        except Exception as exc:
            raise LLMExtractionError(f"LLM relation extraction failed: {exc}") from exc
        relations.extend(
            _relation_to_dict(rel, book_key, page) for rel in extracted_rels or []
        )
    return entities, relations, {"ner_method": "llm", "relation_method": "llm"}
