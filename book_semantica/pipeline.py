"""One-book Semantica pipeline: summary ontology + knowledge graph."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from book_semantica.export_artifacts import export_all
from book_semantica.load_book import count_knowledge, load_knowledge, load_summary
from book_semantica.ontology import normalize_ontology
from book_semantica.paths import (
    BATCH_STATE_FILENAME,
    DEFAULT_BOOK_KEY,
    DEFAULT_LIMIT,
    DEFAULT_MODEL,
    EXTRACT_CACHE_FILENAME,
    REPO_ROOT,
    assert_output_directory,
    assert_safe_output_path,
    book_output_dir,
)
from book_semantica.provenance import record_entities


@dataclass
class RunConfig:
    book_key: str = DEFAULT_BOOK_KEY
    limit: int = DEFAULT_LIMIT
    offset: int = 0
    all_points: bool = False
    force: bool = False
    repo_root: Path = REPO_ROOT
    model: str = DEFAULT_MODEL
    provider: str = "xai"
    output_dir: Path | None = None
    prior_entities: list | None = None
    prior_relations: list | None = None


@dataclass
class AccumulateResult:
    output_dir: Path
    entities: list
    relations: list
    ontology: dict | None
    items: list
    state: dict
    used_methods: dict = field(default_factory=dict)


def _resolve_output_dir(config: RunConfig) -> Path:
    if config.output_dir is not None:
        return assert_output_directory(config.output_dir)
    out_dir = book_output_dir(config.book_key, repo_root=config.repo_root)
    assert_safe_output_path(out_dir / "graph.json")
    return out_dir


def _effective_limit(config: RunConfig) -> int:
    if config.all_points or int(config.limit) == 0:
        return 0
    return int(config.limit)


def _unpack_extract(extracted) -> tuple[list, list, dict]:
    used_methods: dict = {}
    if isinstance(extracted, tuple) and len(extracted) == 3:
        entities, relations, used_methods = extracted
        return list(entities or []), list(relations or []), dict(used_methods or {})
    entities, relations = extracted
    return list(entities or []), list(relations or []), used_methods


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _write_json(path: Path, payload: Any) -> None:
    assert_safe_output_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_extract_cache(out_dir: Path) -> dict:
    payload = _read_json(out_dir / EXTRACT_CACHE_FILENAME) or {}
    return {
        "entities": list(payload.get("entities") or []),
        "relations": list(payload.get("relations") or []),
        "ontology": payload.get("ontology"),
        "covered_end": int(payload.get("covered_end") or 0),
        "used_methods": dict(payload.get("used_methods") or {}),
    }


def accumulate_extract(
    config: RunConfig,
    *,
    extract_entities_relations: Callable,
    generate_ontology: Callable | None = None,
) -> AccumulateResult:
    """LLM-extract only the new knowledge slice and union with the on-disk cache.

    Does not import semantica or build a graph. Writes batch_state.json and
    extract_cache.json under the book output directory.
    """
    out_dir = _resolve_output_dir(config)
    total_items = count_knowledge(config.book_key, repo_root=config.repo_root)
    cache_payload = _read_json(out_dir / EXTRACT_CACHE_FILENAME)
    cache = _load_extract_cache(out_dir)
    offset = max(0, int(config.offset or 0))
    if config.prior_entities is not None:
        cache["entities"] = list(config.prior_entities)
    if config.prior_relations is not None:
        cache["relations"] = list(config.prior_relations)

    # Missing cache must not skip already-covered points with empty accumulation.
    # Do not fall back to batch_state next_offset when extract_cache.json is gone.
    if cache_payload is None:
        covered_end = 0
    else:
        covered_end = int(cache.get("covered_end") or 0)
    if config.force and offset == 0:
        cache = {
            "entities": list(config.prior_entities or []),
            "relations": list(config.prior_relations or []),
            "ontology": None,
            "covered_end": 0,
            "used_methods": {},
        }
        covered_end = 0

    start = max(offset, covered_end)
    limit = _effective_limit(config)
    if limit > 0:
        requested_end = offset + limit
        take = max(0, requested_end - start)
        items = (
            load_knowledge(
                config.book_key,
                limit=take,
                offset=start,
                repo_root=config.repo_root,
            )
            if take
            else []
        )
    else:
        items = load_knowledge(
            config.book_key,
            limit=0,
            offset=start,
            repo_root=config.repo_root,
        )

    used_methods = dict(cache.get("used_methods") or {})
    new_entities: list = []
    new_relations: list = []
    if items:
        new_entities, new_relations, used_methods = _unpack_extract(
            extract_entities_relations(items, config)
        )

    entities = list(cache.get("entities") or []) + new_entities
    relations = list(cache.get("relations") or []) + new_relations
    next_offset = max(covered_end, start + len(items))
    complete = next_offset >= total_items

    ontology = cache.get("ontology")
    if ontology is None and not (config.force and offset == 0):
        ontology = _read_json(out_dir / "ontology.json")
    if ontology is None and generate_ontology is not None:
        summary = load_summary(config.book_key, repo_root=config.repo_root)
        ontology = generate_ontology(summary, config)

    state_payload = {
        "book_key": config.book_key,
        "next_offset": next_offset,
        "total_items": total_items,
        "complete": complete,
        "offset": offset,
        "limit": limit,
        "item_count": len(items),
        "entity_count": len(entities),
        "relation_count": len(relations),
    }
    cache_payload = {
        "entities": entities,
        "relations": relations,
        "ontology": ontology,
        "covered_end": next_offset,
        "used_methods": used_methods,
    }
    _write_json(out_dir / EXTRACT_CACHE_FILENAME, cache_payload)
    _write_json(out_dir / BATCH_STATE_FILENAME, state_payload)
    return AccumulateResult(
        output_dir=out_dir,
        entities=entities,
        relations=relations,
        ontology=ontology,
        items=items,
        state=state_payload,
        used_methods=used_methods,
    )


def run_book(
    config: RunConfig,
    *,
    generate_ontology: Callable | None = None,
    extract_entities_relations: Callable | None = None,
) -> Path:
    ontology_fn = generate_ontology
    if ontology_fn is None:
        from book_semantica.ontology import generate_ontology as ontology_fn
    extract_fn = extract_entities_relations
    if extract_fn is None:
        from book_semantica.extract import extract_entities_relations as extract_fn

    accumulated = accumulate_extract(
        config,
        extract_entities_relations=extract_fn,
        generate_ontology=ontology_fn,
    )
    out_dir = accumulated.output_dir
    entities = accumulated.entities
    relations = accumulated.relations
    used_methods = accumulated.used_methods
    ontology = accumulated.ontology
    if ontology is None:
        summary = load_summary(config.book_key, repo_root=config.repo_root)
        ontology = ontology_fn(summary, config)
    ontology = normalize_ontology(ontology, book_key=config.book_key)

    from book_semantica.graph import (
        build_graph,
        detect_conflicts,
        detect_duplicates,
        restore_entity_provenance,
    )

    conflicts = detect_conflicts(entities, relations)
    graph = build_graph(entities, relations)
    restore_entity_provenance(graph, entities, config.book_key)
    graph.setdefault("metadata", {})
    graph["metadata"]["book_key"] = config.book_key
    graph["metadata"]["limit"] = config.limit
    graph["metadata"]["offset"] = config.offset
    graph["metadata"]["provider"] = config.provider
    if used_methods.get("ner_method"):
        graph["metadata"]["ner_method"] = used_methods["ner_method"]
    if used_methods.get("relation_method"):
        graph["metadata"]["relation_method"] = used_methods["relation_method"]

    duplicates = detect_duplicates(entities, relations)

    manager = None
    try:
        manager = record_entities(graph.get("entities") or entities, config.book_key)
    except Exception:
        manager = None

    export_all(
        out_dir,
        graph=graph,
        ontology=ontology,
        duplicates=duplicates,
        conflicts=conflicts,
        book_key=config.book_key,
        provenance_manager=manager,
    )
    return out_dir


def repair_book(book_key: str, repo_root: Path | None = None) -> Path:
    """Refresh derived artifacts from saved graph.json and ontology.json. No LLM."""
    from book_semantica.export_artifacts import repair_export

    root = repo_root or REPO_ROOT
    out_dir = book_output_dir(book_key, repo_root=root)
    graph_path = out_dir / "graph.json"
    ontology_path = out_dir / "ontology.json"
    if not graph_path.is_file() or not ontology_path.is_file():
        raise FileNotFoundError(f"run first; missing graph or ontology in {out_dir}")
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    ontology = json.loads(ontology_path.read_text(encoding="utf-8"))
    conflicts: list = []
    conflicts_path = out_dir / "conflicts.json"
    if conflicts_path.is_file():
        conflicts = json.loads(conflicts_path.read_text(encoding="utf-8"))
    repair_export(
        out_dir,
        graph=graph,
        ontology=ontology,
        book_key=book_key,
        conflicts=conflicts,
    )
    return out_dir
