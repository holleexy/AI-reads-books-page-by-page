"""List books that have knowledge JSON and a final summary."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from book_semantica.load_book import (
    count_knowledge,
    knowledge_path,
    summary_path,
)
from book_semantica.paths import (
    BATCH_STATE_FILENAME,
    REPO_ROOT,
    book_output_dir,
)

KNOWLEDGE_SUFFIX = "_knowledge.json"


@dataclass
class BookCandidate:
    book_key: str
    knowledge_path: Path
    summary_path: Path
    output_dir: Path
    has_graph: bool
    total_items: int
    batch_state: dict | None = None


def _book_key_from_knowledge_file(path: Path) -> str | None:
    name = path.name
    if not name.endswith(KNOWLEDGE_SUFFIX):
        return None
    key = name[: -len(KNOWLEDGE_SUFFIX)]
    return key or None


def load_batch_state(output_dir: Path) -> dict | None:
    path = Path(output_dir) / BATCH_STATE_FILENAME
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def graph_has_entities(output_dir: Path) -> bool:
    """True when graph.json exists, parses, and has at least one entity.

    Empty files, invalid JSON, and ``{"entities": []}`` are not a real graph.
    Failed writes must be retryable without ``--force``.
    """
    path = Path(output_dir) / "graph.json"
    if not path.is_file():
        return False
    try:
        if path.stat().st_size == 0:
            return False
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    entities = payload.get("entities") or []
    return isinstance(entities, list) and len(entities) >= 1


def should_skip_book(candidate: BookCandidate, *, force: bool = False) -> bool:
    """Skip when a real graph exists and the book is complete, unless --force.

    A real graph without batch_state.json is treated as complete (pilot books).
    Incomplete state (complete=false) is not skipped so the next chunk can run.
    Empty or entity-less graph.json does not skip.
    """
    if force:
        return False
    if not candidate.has_graph:
        return False
    state = candidate.batch_state
    if state is None:
        return True
    return bool(state.get("complete"))


def list_ready_books(repo_root: Path | None = None) -> list[BookCandidate]:
    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    kb_dir = root / "book_analysis" / "knowledge_bases"
    if not kb_dir.is_dir():
        return []
    books: list[BookCandidate] = []
    for path in sorted(kb_dir.glob(f"*{KNOWLEDGE_SUFFIX}")):
        book_key = _book_key_from_knowledge_file(path)
        if not book_key:
            continue
        try:
            summary = summary_path(book_key, repo_root=root)
        except FileNotFoundError:
            continue
        out_dir = book_output_dir(book_key, repo_root=root)
        books.append(
            BookCandidate(
                book_key=book_key,
                knowledge_path=knowledge_path(book_key, repo_root=root),
                summary_path=summary,
                output_dir=out_dir,
                has_graph=graph_has_entities(out_dir),
                total_items=count_knowledge(book_key, repo_root=root),
                batch_state=load_batch_state(out_dir),
            )
        )
    books.sort(key=lambda item: item.book_key)
    return books
