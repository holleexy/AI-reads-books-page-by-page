"""One-book Semantica pipeline: summary ontology + knowledge graph."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from book_semantica.export_artifacts import export_all
from book_semantica.load_book import load_knowledge, load_summary
from book_semantica.ontology import normalize_ontology
from book_semantica.paths import (
    DEFAULT_BOOK_KEY,
    DEFAULT_LIMIT,
    DEFAULT_MODEL,
    REPO_ROOT,
    ForbiddenOutputPath,
    assert_safe_output_path,
    book_output_dir,
)
from book_semantica.provenance import record_entities


@dataclass
class RunConfig:
    book_key: str = DEFAULT_BOOK_KEY
    limit: int = DEFAULT_LIMIT
    repo_root: Path = REPO_ROOT
    model: str = DEFAULT_MODEL
    provider: str = "xai"
    output_dir: Path | None = None


def _resolve_output_dir(config: RunConfig) -> Path:
    if config.output_dir is not None:
        candidate = Path(config.output_dir)
        if candidate.suffix:
            assert_safe_output_path(candidate)
            raise ForbiddenOutputPath(
                f"output_dir must be a directory, not a file: {candidate}"
            )
        assert_safe_output_path(candidate / "graph.json")
        return candidate
    out_dir = book_output_dir(config.book_key, repo_root=config.repo_root)
    assert_safe_output_path(out_dir / "graph.json")
    return out_dir


def run_book(
    config: RunConfig,
    *,
    generate_ontology: Callable | None = None,
    extract_entities_relations: Callable | None = None,
) -> Path:
    out_dir = _resolve_output_dir(config)
    items = load_knowledge(
        config.book_key,
        limit=config.limit,
        repo_root=config.repo_root,
    )
    summary = load_summary(config.book_key, repo_root=config.repo_root)

    ontology_fn = generate_ontology
    if ontology_fn is None:
        from book_semantica.ontology import generate_ontology as ontology_fn
    extract_fn = extract_entities_relations
    if extract_fn is None:
        from book_semantica.extract import extract_entities_relations as extract_fn

    ontology = normalize_ontology(ontology_fn(summary, config), book_key=config.book_key)
    extracted = extract_fn(items, config)
    used_methods: dict = {}
    if isinstance(extracted, tuple) and len(extracted) == 3:
        entities, relations, used_methods = extracted
    else:
        entities, relations = extracted

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
    import json

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
