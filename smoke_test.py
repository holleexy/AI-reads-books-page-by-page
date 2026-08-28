#!/usr/bin/env python3
"""Smoke test: exercise real API path (call_api -> process_page) with one PDF page."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pathlib import Path
import fitz
from read_books import BookConfig, create_client, process_page, PRIMARY_MODEL

def main():
    client = create_client()
    print(
        f"client OK, provider={client.provider}, auth_mode={client.auth_mode}, "
        f"base_url={client.base_url}, model={PRIMARY_MODEL}"
    )

    # Use real page text from meditations.pdf (page 10, likely content)
    with fitz.open("meditations.pdf") as doc:
        page_text = doc[10].get_text()
    print(f"page text sample: {page_text[:80]!r}...")

    config = BookConfig(pdf_path=Path("meditations.pdf"))
    result = process_page(client, page_text, [], 10, config)
    assert result is not None, "process_page returned None (parse failed)"
    print(f"RESULT: {len(result)} knowledge points extracted")
    assert len(result) > 0, "no knowledge extracted from content page"
    print("SMOKE OK")

if __name__ == "__main__":
    main()
