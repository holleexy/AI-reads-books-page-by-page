"""LLM NER and relation extraction over knowledge points.

Calls Semantica's llm methods directly. Does not use NamedEntityRecognizer
or RelationExtractor, because those fall back to English pattern NER.
"""

from __future__ import annotations

from typing import Any

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import xai_oauth
from book_semantica.paths import DEFAULT_MODEL
from book_semantica.provenance import stamp_entity, stamp_relation


class LLMExtractionError(RuntimeError):
    """xAI / LLM extraction failed. Pattern NER was not used."""


_oauth_refresh_lock = threading.Lock()


def _is_auth_error(exc: Exception) -> bool:
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    if "authentication" in name or "permissiondenied" in name:
        return True
    return any(
        token in msg
        for token in (
            "unauthenticated",
            "bad-credentials",
            "invalid_api_key",
            "unauthorized",
            "403",
        )
    )


def _extract_llm_kwargs(config) -> dict:
    model = getattr(config, "model", None) or DEFAULT_MODEL
    kwargs = {
        "provider": "xai",
        "llm_model": model,
        "model": model,
        "silent_fail": False,
    }
    api_key = os.environ.get("XAI_API_KEY")
    if api_key:
        kwargs["api_key"] = api_key
    return kwargs


def _refresh_xai_access_token() -> str | None:
    with _oauth_refresh_lock:
        token = xai_oauth.resolve_access_token(force_refresh=True)
        if token:
            os.environ["XAI_API_KEY"] = token
        return token


def _call_llm_with_auth_retry(fn, *args, fail_label: str, config):
    kwargs = _extract_llm_kwargs(config)
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        if not _is_auth_error(exc):
            raise LLMExtractionError(f"{fail_label}: {exc}") from exc
        token = _refresh_xai_access_token()
        if not token:
            raise LLMExtractionError(f"{fail_label}: {exc}") from exc
        retry_kwargs = _extract_llm_kwargs(config)
        retry_kwargs["api_key"] = token
        try:
            return fn(*args, **retry_kwargs)
        except Exception as retry_exc:
            raise LLMExtractionError(f"{fail_label}: {retry_exc}") from retry_exc


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


def _extract_concurrency(config) -> int:
    raw = getattr(config, "extract_concurrency", None)
    if raw is None:
        raw = os.environ.get("EXTRACT_CONCURRENCY", "2")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 2
    return max(1, min(4, value))


def _extract_one_item(
    item: dict,
    config,
    extract_ents,
    extract_rels,
) -> tuple[list[dict], list[dict]]:
    text = item.get("text") or ""
    if not text.strip():
        return [], []
    book_key = getattr(config, "book_key")
    page = item.get("page")
    extracted = _call_llm_with_auth_retry(
        extract_ents,
        text,
        fail_label="LLM NER failed",
        config=config,
    )
    _reject_pattern_entities(extracted)
    entities = [_entity_to_dict(ent, book_key, page) for ent in extracted or []]
    if not extracted:
        return entities, []
    extracted_rels = _call_llm_with_auth_retry(
        extract_rels,
        text,
        extracted,
        fail_label="LLM relation extraction failed",
        config=config,
    )
    relations = [_relation_to_dict(rel, book_key, page) for rel in extracted_rels or []]
    return entities, relations


def _extract_items(
    items: list[dict],
    config,
    extract_ents,
    extract_rels,
) -> tuple[list[dict], list[dict], dict[str, str]]:
    workers = _extract_concurrency(config)
    indexed = list(enumerate(items))
    slots: list[tuple[list[dict], list[dict]] | None] = [None] * len(indexed)

    def run_one(pair: tuple[int, dict]) -> tuple[int, list[dict], list[dict]]:
        index, item = pair
        ents, rels = _extract_one_item(item, config, extract_ents, extract_rels)
        return index, ents, rels

    if workers == 1 or len(items) <= 1:
        for index, item in indexed:
            ents, rels = _extract_one_item(item, config, extract_ents, extract_rels)
            slots[index] = (ents, rels)
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(run_one, pair) for pair in indexed]
            try:
                for future in as_completed(futures):
                    index, ents, rels = future.result()
                    slots[index] = (ents, rels)
            except Exception:
                for future in futures:
                    future.cancel()
                raise

    entities: list[dict] = []
    relations: list[dict] = []
    for slot in slots:
        if slot is None:
            continue
        ents, rels = slot
        entities.extend(ents)
        relations.extend(rels)
    return entities, relations, {"ner_method": "llm", "relation_method": "llm"}


def extract_entities_relations(
    items: list[dict], config
) -> tuple[list[dict], list[dict], dict[str, str]]:
    from book_semantica.xai_provider import register_xai_provider
    from semantica.semantic_extract.methods import (
        get_entity_method,
        get_relation_method,
    )

    register_xai_provider()
    extract_ents = get_entity_method("llm")
    extract_rels = get_relation_method("llm")
    return _extract_items(items, config, extract_ents, extract_rels)
