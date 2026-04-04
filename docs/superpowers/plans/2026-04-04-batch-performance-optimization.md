# Batch Performance Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce batch processing time from ~12 hours to ~3-4 hours by parallelizing book processing, eliminating interval analysis overhead, and skipping non-content pages locally.

**Architecture:** Three independent changes to the existing pipeline: (1) `run_all_books.py` gets `ThreadPoolExecutor` to process 2-3 books concurrently — each book keeps its own isolated state files so no locking is needed; (2) batch mode disables interval analysis, running only the final summary; (3) a local text heuristic in `read_books.py` skips obviously empty/boilerplate pages before making an API call.

**Tech Stack:** Python 3.12, concurrent.futures (stdlib), PyMuPDF, anthropic SDK (Z.AI endpoint)

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `run_all_books.py` | Modify | Add ThreadPoolExecutor book-level parallelism, per-worker client, progress display |
| `read_books.py` | Modify | Add `should_skip_locally()` heuristic, make interval analysis optional |
| `tests/test_skip_heuristic.py` | Create | Tests for local page skip logic |
| `tests/test_parallel_batch.py` | Create | Tests for parallel batch orchestration |

---

### Task 1: Local Page Skip Heuristic

**Files:**
- Create: `tests/test_skip_heuristic.py`
- Modify: `read_books.py:156-192` (process_page function)

This adds a cheap local check before sending a page to the API. Pages that are blank, very short (< 30 chars), or match common boilerplate patterns (TOC, copyright, index) get skipped without an API call.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_skip_heuristic.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from read_books import should_skip_locally


def test_blank_page():
    assert should_skip_locally("") is True
    assert should_skip_locally("   \n\n  ") is True


def test_very_short_page():
    assert should_skip_locally("42") is True
    assert should_skip_locally("Page 15") is True


def test_copyright_page():
    text = "Copyright 2024 Publisher Inc. All rights reserved. ISBN 978-4-123456-78-9"
    assert should_skip_locally(text) is True


def test_toc_page():
    text = "目次\n第1章 はじめに...........3\n第2章 基本概念...........25\n第3章 応用...........47"
    assert should_skip_locally(text) is True


def test_real_content_not_skipped():
    text = "リーダーシップとは、他者に影響を与え、共通の目標に向かって行動を促す能力である。これは生まれつきの資質ではなく、学習と実践を通じて開発できるスキルである。"
    assert should_skip_locally(text) is False


def test_short_but_meaningful_not_skipped():
    text = "第1章 戦略的思考の基本原則と実践的なフレームワーク"
    assert should_skip_locally(text) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/m3dp6/AI-reads-books-page-by-page && python -m pytest tests/test_skip_heuristic.py -v`
Expected: FAIL — `ImportError: cannot import name 'should_skip_locally' from 'read_books'`

- [ ] **Step 3: Implement should_skip_locally()**

Add this function in `read_books.py` after the `atomic_write_text` function (after line 123):

```python
# --- Local skip heuristic (avoids API call for obvious non-content) ---

import re

_SKIP_PATTERNS = re.compile(
    r"(?:目次|contents|copyright|isbn|all rights reserved|"
    r"参考文献|references|bibliography|索引|index|"
    r"acknowledgment|謝辞|奥付|発行)",
    re.IGNORECASE,
)


def should_skip_locally(page_text: str) -> bool:
    """Return True if the page is obviously non-content and can be skipped without an API call."""
    stripped = page_text.strip()
    if len(stripped) < 30:
        return True
    if _SKIP_PATTERNS.search(stripped) and len(stripped) < 500:
        return True
    return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/m3dp6/AI-reads-books-page-by-page && python -m pytest tests/test_skip_heuristic.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Wire heuristic into process_page**

In `read_books.py`, modify `process_page` (line 156) to check before API call:

```python
def process_page(client: anthropic.Anthropic, page_text: str, knowledge: list[str], page_num: int, config: BookConfig) -> list[str] | None:
    """Process a single page. Returns updated knowledge list, or None if all parse retries failed."""
    if should_skip_locally(page_text):
        print(colored(f"  Skipping page {page_num + 1} (local heuristic)", "yellow"))
        return knowledge

    print(colored(f"\nProcessing page {page_num + 1}...", "yellow"))
    # ... rest of function unchanged ...
```

- [ ] **Step 6: Run all tests**

Run: `cd C:/Users/m3dp6/AI-reads-books-page-by-page && python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
cd C:/Users/m3dp6/AI-reads-books-page-by-page
git add tests/test_skip_heuristic.py read_books.py
git commit -m "perf: add local page skip heuristic to avoid API calls for blank/boilerplate pages"
```

---

### Task 2: Disable Interval Analysis in Batch Mode

**Files:**
- Modify: `run_all_books.py:70-76` (BookConfig construction)
- Modify: `read_books.py:336-344` (interval analysis block)

Interval summaries add ~485 extra API calls across all books. They are redundant because a final summary is always generated. Setting `analysis_interval=None` already disables them per existing code at `read_books.py:336`.

- [ ] **Step 1: Write the test**

```python
# tests/test_parallel_batch.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from read_books import BookConfig


def test_analysis_interval_none_disables_interval():
    """analysis_interval=None should disable interval analysis."""
    config = BookConfig(
        pdf_path=Path("dummy.pdf"),
        analysis_interval=None,
    )
    assert config.analysis_interval is None
```

- [ ] **Step 2: Run test to verify it passes**

Run: `cd C:/Users/m3dp6/AI-reads-books-page-by-page && python -m pytest tests/test_parallel_batch.py::test_analysis_interval_none_disables_interval -v`
Expected: PASS (existing code already supports this)

- [ ] **Step 3: Set analysis_interval=None in run_all_books.py**

In `run_all_books.py`, change line 73 from `analysis_interval=30` to `analysis_interval=None`:

```python
        config = BookConfig(
            pdf_path=pdf_path,
            base_dir=RESULTS_DIR,
            analysis_interval=None,  # batch mode: final summary only
            test_pages=None,
        )
```

- [ ] **Step 4: Commit**

```bash
cd C:/Users/m3dp6/AI-reads-books-page-by-page
git add run_all_books.py tests/test_parallel_batch.py
git commit -m "perf: disable interval analysis in batch mode (final summary only)"
```

---

### Task 3: Book-Level Parallelism

**Files:**
- Modify: `run_all_books.py` (full rewrite of `main()`)

This is the highest-impact change. Each book has isolated state files (`*_knowledge.json`, `*_progress.json`, `*_status.json`), so no locking is needed. Each thread gets its own `anthropic.Anthropic` client.

- [ ] **Step 1: Add test for parallel orchestration**

Append to `tests/test_parallel_batch.py`:

```python
import os


def test_max_book_workers_env_default():
    """MAX_BOOK_WORKERS defaults to 2 when env var is not set."""
    os.environ.pop("MAX_BOOK_WORKERS", None)
    # Re-import to pick up the default
    import importlib
    import run_all_books
    importlib.reload(run_all_books)
    assert run_all_books.MAX_BOOK_WORKERS == 2


def test_max_book_workers_env_override():
    """MAX_BOOK_WORKERS can be overridden via environment variable."""
    os.environ["MAX_BOOK_WORKERS"] = "4"
    import importlib
    import run_all_books
    importlib.reload(run_all_books)
    assert run_all_books.MAX_BOOK_WORKERS == 4
    os.environ.pop("MAX_BOOK_WORKERS", None)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/m3dp6/AI-reads-books-page-by-page && python -m pytest tests/test_parallel_batch.py -v`
Expected: FAIL — `AttributeError: module 'run_all_books' has no attribute 'MAX_BOOK_WORKERS'`

- [ ] **Step 3: Rewrite run_all_books.py with ThreadPoolExecutor**

Full replacement of `run_all_books.py`:

```python
#!/usr/bin/env python3
"""Batch process all Kindle PDFs with GLM 5.1 — parallel book processing."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import os
import sys
import json

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

    known_via_status = set()
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
```

- [ ] **Step 4: Run all tests**

Run: `cd C:/Users/m3dp6/AI-reads-books-page-by-page && python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 5: Smoke test with dry run**

Run: `cd C:/Users/m3dp6/AI-reads-books-page-by-page && set -a && source C:/Users/m3dp6/obsidian-work/.env && set +a && python -c "from run_all_books import get_completed_books, MAX_BOOK_WORKERS; c=get_completed_books(); print(f'Completed: {len(c)}, Workers: {MAX_BOOK_WORKERS}')"`
Expected: `Completed: 4, Workers: 2` (Atama_noii, BUILDING_BLOCKS, Eigyou_sukiru, Muhai_Eigyou test-mode excluded)

- [ ] **Step 6: Commit**

```bash
cd C:/Users/m3dp6/AI-reads-books-page-by-page
git add run_all_books.py tests/test_parallel_batch.py
git commit -m "perf: add book-level parallelism with ThreadPoolExecutor (2 workers default)"
```

---

### Task 4: Integration Verification

- [ ] **Step 1: Run full test suite**

Run: `cd C:/Users/m3dp6/AI-reads-books-page-by-page && python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 2: Start batch processing**

```bash
cd C:/Users/m3dp6/AI-reads-books-page-by-page
set -a && source C:/Users/m3dp6/obsidian-work/.env && set +a
python run_all_books.py
```

Expected: Resumes entaapuraizuseerusu from page 181 AND starts the next unprocessed book in parallel.

- [ ] **Step 3: Monitor for rate limits**

Watch for `API error: ... 429` messages in the first 2-3 minutes. If 429s appear frequently:
- Reduce workers: `MAX_BOOK_WORKERS=1 python run_all_books.py`
- Or add a sleep in `call_api` retry logic
