"""CLI for one-book Semantica runs, queries, and the book HTML viewer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from book_semantica.paths import (
    DEFAULT_BOOK_KEY,
    DEFAULT_LIMIT,
    DEFAULT_MODEL,
    DEFAULT_VIEWER_PORT,
    REPO_ROOT,
    book_output_dir,
)
from book_semantica.query import neighbors, shortest_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="book_semantica",
        description="Build or query a per-book Semantica graph (not the Hermes graph).",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="run",
        choices=["run", "query", "serve", "repair"],
        help="run (default), query, or serve",
    )
    parser.add_argument("--book-key", default=DEFAULT_BOOK_KEY)
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help="knowledge points to extract (default 80)",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--name", help="entity name for neighbor query")
    parser.add_argument("--source", help="path start name")
    parser.add_argument("--target", help="path end name")
    parser.add_argument("--port", type=int, default=DEFAULT_VIEWER_PORT)
    parser.add_argument(
        "--explorer",
        action="store_true",
        help="optional: bind semantica.explorer to the book graph (still not 8766)",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
    )
    return parser.parse_args(argv)


def _graph_path(book_key: str, repo_root: Path) -> Path:
    return book_output_dir(book_key, repo_root=repo_root) / "graph.json"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "query":
        path = _graph_path(args.book_key, args.repo_root)
        if not path.is_file():
            print(f"graph not found: {path}", file=sys.stderr)
            return 1
        graph = json.loads(path.read_text(encoding="utf-8"))
        if args.source and args.target:
            print(json.dumps(shortest_path(graph, args.source, args.target), ensure_ascii=False, indent=2))
            return 0
        if not args.name:
            print("query needs --name, or --source and --target", file=sys.stderr)
            return 2
        print(json.dumps(neighbors(graph, args.name), ensure_ascii=False, indent=2))
        return 0
    if args.command == "serve":
        from book_semantica.serve import serve_explorer, serve_html

        out_dir = book_output_dir(args.book_key, repo_root=args.repo_root)
        if args.explorer:
            serve_explorer(out_dir / "graph.json", port=args.port)
        else:
            serve_html(out_dir, port=args.port)
        return 0
    if args.command == "repair":
        from book_semantica.pipeline import repair_book

        out_dir = repair_book(args.book_key, repo_root=args.repo_root)
        print(out_dir)
        return 0

    from book_semantica.pipeline import RunConfig, run_book

    out_dir = run_book(
        RunConfig(
            book_key=args.book_key,
            limit=args.limit,
            repo_root=args.repo_root,
            model=args.model,
        )
    )
    print(out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
