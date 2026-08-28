"""Command-line options for reading one or more PDFs."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunOptions:
    test_pages: int | None
    analysis_interval: int | None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="read_books.py",
        description="Extract knowledge from PDF books with xAI Grok.",
    )
    parser.add_argument(
        "pdfs",
        nargs="+",
        metavar="PDF",
        help="PDF file, or a directory whose top-level *.pdf files will be read",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=None,
        metavar="N",
        help="process only the first N pages (default: entire book)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=20,
        metavar="N",
        help="write an interval summary every N pages; 0 disables (default: 20)",
    )
    args = parser.parse_args(argv)
    if args.pages is not None and args.pages <= 0:
        parser.error("--pages must be a positive integer")
    if args.interval < 0:
        parser.error("--interval must be 0 or a positive integer")
    return args


def run_options_from_args(args: argparse.Namespace) -> RunOptions:
    interval = args.interval if args.interval > 0 else None
    return RunOptions(test_pages=args.pages, analysis_interval=interval)


def resolve_pdf_paths(values: list[str]) -> list[Path]:
    resolved: list[Path] = []
    seen: set[Path] = set()
    for raw in values:
        path = Path(raw).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {raw}")
        if path.is_dir():
            pdfs = _pdfs_in_directory(path)
            if not pdfs:
                raise FileNotFoundError(f"No PDFs found in {path}")
            for pdf in pdfs:
                _append_unique(resolved, seen, pdf)
            continue
        if path.suffix.lower() != ".pdf":
            raise ValueError(f"Not a PDF: {raw}")
        _append_unique(resolved, seen, path.resolve())
    return resolved


def _pdfs_in_directory(path: Path) -> list[Path]:
    pdfs = [
        child.resolve()
        for child in path.iterdir()
        if child.is_file() and child.suffix.lower() == ".pdf"
    ]
    return sorted(pdfs, key=lambda item: item.name.lower())


def _append_unique(resolved: list[Path], seen: set[Path], pdf: Path) -> None:
    if pdf in seen:
        return
    seen.add(pdf)
    resolved.append(pdf)
