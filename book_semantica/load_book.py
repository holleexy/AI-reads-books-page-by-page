"""Load a book's knowledge JSON and latest final summary."""

from __future__ import annotations

import json
from pathlib import Path

from book_semantica.paths import REPO_ROOT


def normalize_knowledge_item(raw) -> dict | None:
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        return {"text": text, "page": None}
    if isinstance(raw, dict):
        text = str(raw.get("text") or "").strip()
        if not text:
            return None
        page = raw.get("page")
        if page is not None:
            try:
                page = int(page)
            except (TypeError, ValueError):
                page = None
        return {"text": text, "page": page}
    return None


def normalize_knowledge(raw_list) -> list[dict]:
    items: list[dict] = []
    for raw in raw_list or []:
        item = normalize_knowledge_item(raw)
        if item:
            items.append(item)
    return items


def knowledge_path(book_key: str, repo_root: Path | None = None) -> Path:
    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    return root / "book_analysis" / "knowledge_bases" / f"{book_key}_knowledge.json"


def summary_path(book_key: str, repo_root: Path | None = None) -> Path:
    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    summaries = root / "book_analysis" / "summaries"
    matches = sorted(summaries.glob(f"{book_key}_final_*.md"))
    if not matches:
        raise FileNotFoundError(
            f"no final summary for {book_key} under {summaries}"
        )
    return matches[-1]


def count_knowledge(book_key: str, repo_root: Path | None = None) -> int:
    return len(load_knowledge(book_key, limit=None, offset=0, repo_root=repo_root))


def load_knowledge(
    book_key: str,
    limit: int | None = None,
    repo_root: Path | None = None,
    offset: int = 0,
) -> list[dict]:
    path = knowledge_path(book_key, repo_root=repo_root)
    if not path.is_file():
        raise FileNotFoundError(f"knowledge JSON not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = normalize_knowledge(payload.get("knowledge") or [])
    start = max(0, int(offset or 0))
    items = items[start:]
    if limit is not None and int(limit) > 0:
        items = items[: int(limit)]
    return items


def load_summary(book_key: str, repo_root: Path | None = None) -> str:
    path = summary_path(book_key, repo_root=repo_root)
    return path.read_text(encoding="utf-8")
