"""Paths and guards for the book-side Semantica pipeline."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_SEMANTICA_PYTHON = Path(
    "/var/lib/happy/.local/share/semantica/venv/bin/python"
)
HERMES_GRAPH_PATH = Path(
    "/var/lib/happy/.local/state/hermes/semantica-knowledge-work.json"
)
SEMANTICA_OUTPUT_ROOT_NAME = "book_analysis/semantica"
DEFAULT_VIEWER_PORT = 8767
HERMES_EXPLORER_PORT = 8766
DEFAULT_LIMIT = 80
DEFAULT_BOOK_KEY = "労務入門.ocr"
DEFAULT_MODEL = "grok-4.6"
BATCH_STATE_FILENAME = "batch_state.json"
EXTRACT_CACHE_FILENAME = "extract_cache.json"
MANIFEST_RELPATH = Path("book_analysis/semantica/manifest.jsonl")


class ForbiddenOutputPath(RuntimeError):
    """Raised when an output path would write the Hermes work graph."""


def resolve_semantica_python() -> Path:
    raw = os.environ.get("SEMANTICA_PYTHON")
    if raw:
        return Path(raw).expanduser().resolve()
    return DEFAULT_SEMANTICA_PYTHON


def book_output_dir(book_key: str, repo_root: Path | None = None) -> Path:
    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    return root / "book_analysis" / "semantica" / book_key


def assert_safe_output_path(path: Path | str) -> Path:
    candidate = Path(path)
    try:
        resolved = candidate.resolve()
    except OSError as exc:
        raise ForbiddenOutputPath(
            f"cannot resolve output path {candidate}: {exc}"
        ) from exc
    forbidden = HERMES_GRAPH_PATH.resolve()
    if resolved == forbidden:
        raise ForbiddenOutputPath(
            f"refusing to write Hermes graph: {forbidden}"
        )
    return resolved


def assert_output_directory(path: Path | str) -> Path:
    """Treat existing files and the Hermes work graph as forbidden file outputs.

    A path is a file only if it already exists as a file, or it is exactly
    HERMES_GRAPH_PATH (even when that file does not exist yet). Book keys such
    as ``採用入門.ocr`` are directories: a suffix alone is not a file.
    Nonexistent paths are directories to create.
    """
    candidate = Path(path)
    if candidate.is_file():
        assert_safe_output_path(candidate)
        raise ForbiddenOutputPath(
            f"output_dir must be a directory, not a file: {candidate}"
        )
    assert_safe_output_path(candidate)
    assert_safe_output_path(candidate / "graph.json")
    return candidate


def assert_viewer_port(port: int) -> int:
    if int(port) == HERMES_EXPLORER_PORT:
        raise ValueError(
            f"port {HERMES_EXPLORER_PORT} is the Hermes explorer; "
            f"use {DEFAULT_VIEWER_PORT} for book graphs"
        )
    return int(port)
