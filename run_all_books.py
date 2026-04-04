#!/usr/bin/env python3
"""Batch process all Kindle PDFs with GLM 5.1 — parallel book processing."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import os
import sys
import json

# Auto-load .env (supports PowerShell where `source .env` doesn't work)
from dotenv import load_dotenv
load_dotenv()  # local .env
load_dotenv(Path.home() / "obsidian-work" / ".env")  # fallback

sys.path.insert(0, str(Path(__file__).parent))
from read_books import BookConfig, create_client, process_book
from termcolor import colored

KINDLE_PDFS_DIR = Path("kindle_pdfs")
RESULTS_DIR = Path("book_analysis")
MAX_BOOK_WORKERS = int(os.getenv("MAX_BOOK_WORKERS", "2"))


def get_completed_books():
    """Check status.json manifests; fall back to legacy final-summary detection."""
    completed = set()
    knowledge_dir = RESULTS_DIR / "knowledge_bases"

    # Primary: status.json manifests (T3)
    known_via_status = set()  # All books with a status.json (regardless of completion)
    if knowledge_dir.exists():
        for f in knowledge_dir.glob("*_status.json"):
            try:
                with open(f, 'r', encoding='utf-8') as fh:
                    status = json.load(fh)
                book_key = status.get("book_key", f.stem.replace("_status", ""))
                known_via_status.add(book_key)
                if status.get("summary_generated") and not status.get("test_mode"):
                    completed.add(book_key)
            except (json.JSONDecodeError, KeyError):
                continue

    # Fallback: legacy detection for books processed before status.json was introduced
    # Skip books that already have a status.json (status.json is authoritative)
    summaries_dir = RESULTS_DIR / "summaries"
    if summaries_dir.exists():
        for f in summaries_dir.glob("*_final_*.md"):
            book_name = f.name.rsplit("_final_", 1)[0]
            if book_name not in completed and book_name not in known_via_status:
                print(colored(f"  [legacy] {book_name} detected via final summary (no status.json)", "yellow"))
                completed.add(book_name)

    return completed


def process_one_book(pdf_path: Path) -> str:
    """Process a single book in its own thread with its own API client."""
    client = create_client()
    config = BookConfig(
        pdf_path=pdf_path,
        base_dir=RESULTS_DIR,
        analysis_interval=None,  # batch mode: final summary only
        test_pages=None,
    )
    process_book(client, config)
    return pdf_path.stem


def main():
    pdfs = sorted(KINDLE_PDFS_DIR.glob("*.pdf"))
    if not pdfs:
        print(colored(f"No PDFs found in {KINDLE_PDFS_DIR}/", "red"))
        sys.exit(1)

    completed = get_completed_books()
    remaining = [p for p in pdfs if p.stem not in completed]

    # Codex review: dedupe by book_key to prevent file write races
    seen_keys = set()
    deduped = []
    for p in remaining:
        if p.stem not in seen_keys:
            seen_keys.add(p.stem)
            deduped.append(p)
    remaining = deduped

    print(colored(f"\nBooks: {len(pdfs)} total, {len(completed)} done, {len(remaining)} remaining", "cyan"))
    print(colored(f"Workers: {MAX_BOOK_WORKERS} parallel", "cyan"))
    for i, p in enumerate(remaining, 1):
        print(colored(f"  {i}. {p.stem}", "white"))

    if not remaining:
        print(colored("\nAll books already processed!", "green"))
        return

    print(colored(f"\nStarting parallel batch processing...\n", "cyan"))

    done_count = 0
    fail_count = 0

    with ThreadPoolExecutor(max_workers=MAX_BOOK_WORKERS) as pool:
        futures = {pool.submit(process_one_book, pdf): pdf for pdf in remaining}
        for future in as_completed(futures):
            pdf = futures[future]
            try:
                future.result()
                done_count += 1
                print(colored(f"\n[DONE {done_count}/{len(remaining)}] {pdf.stem}", "green", attrs=["bold"]))
            except Exception as e:
                fail_count += 1
                print(colored(f"\n[FAIL] {pdf.stem}: {e}", "red"))

    print(colored(f"\n{'='*60}", "green"))
    print(colored(f"  Batch complete: {done_count} done, {fail_count} failed", "green", attrs=["bold"]))
    print(colored(f"{'='*60}", "green"))


if __name__ == "__main__":
    main()
