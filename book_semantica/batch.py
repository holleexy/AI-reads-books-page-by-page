"""Plan and run per-book Semantica jobs. Does not import semantica."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from book_semantica.discover import (
    BookCandidate,
    list_ready_books,
    load_batch_state,
    should_skip_book,
)
from book_semantica.paths import (
    DEFAULT_LIMIT,
    EXTRACT_CACHE_FILENAME,
    MANIFEST_RELPATH,
    REPO_ROOT,
    assert_output_directory,
    assert_safe_output_path,
    book_output_dir,
)

DEFAULT_BATCH_LIMIT = DEFAULT_LIMIT


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _guard_output_dir(output_dir: Path | str | None) -> None:
    if output_dir is None:
        return
    assert_output_directory(output_dir)


def manifest_path(repo_root: Path | None = None) -> Path:
    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    path = root / MANIFEST_RELPATH
    assert_safe_output_path(path)
    return path


def append_manifest(repo_root: Path | None, row: dict) -> Path:
    path = manifest_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def plan_books(repo_root: Path | None = None, *, force: bool = False) -> list[dict]:
    rows = []
    for book in list_ready_books(repo_root=repo_root):
        skip = should_skip_book(book, force=force)
        state = book.batch_state or {}
        rows.append(
            {
                "book_key": book.book_key,
                "status": "skip" if skip else "pending",
                "total_items": book.total_items,
                "has_graph": book.has_graph,
                "complete": bool(state.get("complete")) if state else book.has_graph,
                "next_offset": int(state["next_offset"]) if "next_offset" in state else 0,
                "output_dir": str(book.output_dir),
            }
        )
    return rows


def format_plan(rows: list[dict]) -> str:
    pending = sum(1 for row in rows if row.get("status") == "pending")
    skipped = sum(1 for row in rows if row.get("status") == "skip")
    lines = ["status\tbook_key\ttotal_items\toutput_dir"]
    for row in rows:
        lines.append(
            f"{row.get('status')}\t{row.get('book_key')}\t"
            f"{row.get('total_items')}\t{row.get('output_dir')}"
        )
    lines.append(f"pending={pending} skip={skipped}")
    return "\n".join(lines) + "\n"


def _extract_cache_readable(output_dir: Path) -> bool:
    path = Path(output_dir) / EXTRACT_CACHE_FILENAME
    if not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return False
    return isinstance(payload, dict)


def _effective_offset(
    book: BookCandidate,
    *,
    offset: int,
    force: bool,
    output_dir: Path | None = None,
) -> int:
    if force:
        return int(offset or 0)
    state = book.batch_state or {}
    if state and not state.get("complete") and "next_offset" in state:
        cache_dir = Path(output_dir) if output_dir is not None else book.output_dir
        if not _extract_cache_readable(cache_dir):
            return int(offset or 0)
        return int(state["next_offset"])
    return int(offset or 0)


def _book_output_dir(
    book: BookCandidate,
    *,
    repo_root: Path,
    output_dir: Path | None,
) -> Path:
    if output_dir is not None:
        return Path(output_dir) / book.book_key
    return book_output_dir(book.book_key, repo_root=repo_root)


def _row_for(
    book: BookCandidate,
    *,
    status: str,
    offset: int,
    limit: int,
    output: Path,
    error: str | None = None,
    item_count: int | None = None,
) -> dict:
    row = {
        "book_key": book.book_key,
        "status": status,
        "offset": offset,
        "limit": limit,
        "item_count": item_count if item_count is not None else book.total_items,
        "total_items": book.total_items,
        "output_dir": str(output),
        "timestamp": _utc_now(),
    }
    if error:
        row["error"] = error
    return row


def run_batch(
    repo_root: Path | None = None,
    *,
    dry_run: bool = False,
    force: bool = False,
    offset: int = 0,
    limit: int = DEFAULT_BATCH_LIMIT,
    all_points: bool = False,
    output_dir: Path | str | None = None,
    book_keys: list[str] | None = None,
    run_book_fn: Callable | None = None,
    generate_ontology: Callable | None = None,
    extract_entities_relations: Callable | None = None,
) -> list[dict]:
    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    _guard_output_dir(output_dir)
    manifest_path(root)

    wanted = set(book_keys) if book_keys else None
    books = [
        book
        for book in list_ready_books(repo_root=root)
        if wanted is None or book.book_key in wanted
    ]
    chunk = 0 if all_points else int(limit)
    rows: list[dict] = []

    process_fn = run_book_fn
    if not dry_run:
        from book_semantica.pipeline import RunConfig
        if process_fn is None:
            from book_semantica.pipeline import run_book as process_fn

    for book in books:
        skip = should_skip_book(book, force=force)
        out = _book_output_dir(book, repo_root=root, output_dir=Path(output_dir) if output_dir else None)
        assert_safe_output_path(out / "graph.json")
        book_offset = _effective_offset(
            book, offset=offset, force=force, output_dir=out
        )
        if skip:
            row = _row_for(
                book,
                status="skip",
                offset=book_offset,
                limit=chunk,
                output=out,
            )
            rows.append(row)
            if not dry_run:
                append_manifest(root, row)
            continue
        if dry_run:
            rows.append(
                _row_for(
                    book,
                    status="pending",
                    offset=book_offset,
                    limit=chunk,
                    output=out,
                )
            )
            continue
        config = RunConfig(
            book_key=book.book_key,
            limit=chunk,
            offset=book_offset,
            all_points=all_points,
            repo_root=root,
            output_dir=out,
            force=force,
        )
        try:
            process_fn(
                config,
                generate_ontology=generate_ontology,
                extract_entities_relations=extract_entities_relations,
            )
            state = load_batch_state(out) or {}
            slice_count = state.get("item_count")
            row = _row_for(
                book,
                status="success",
                offset=config.offset,
                limit=chunk,
                output=out,
                item_count=int(slice_count) if slice_count is not None else None,
            )
        except Exception as exc:
            row = _row_for(
                book,
                status="fail",
                offset=config.offset,
                limit=chunk,
                output=out,
                error=str(exc),
            )
        rows.append(row)
        append_manifest(root, row)
    return rows
