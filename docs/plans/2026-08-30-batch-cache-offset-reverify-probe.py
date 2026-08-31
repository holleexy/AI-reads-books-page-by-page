#!/usr/bin/env python3
"""Adversarial PROBE for missing/unreadable extract_cache vs run_batch.

Does not live-call xAI. Does not import semantica. Uses production run_batch
(no run_book_fn). Graph/export/extract/ontology are mocked.
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from book_semantica.batch import run_batch
from book_semantica.paths import BATCH_STATE_FILENAME, EXTRACT_CACHE_FILENAME


KNOWLEDGE = [
    {"text": "命題A", "page": 1},
    {"text": "命題B", "page": 2},
    {"text": "命題C", "page": 3},
    {"text": "命題D", "page": 4},
]


def write_book(root: Path, book_key: str) -> Path:
    kb = root / "book_analysis" / "knowledge_bases"
    summaries = root / "book_analysis" / "summaries"
    kb.mkdir(parents=True, exist_ok=True)
    summaries.mkdir(parents=True, exist_ok=True)
    (kb / f"{book_key}_knowledge.json").write_text(
        json.dumps({"knowledge": KNOWLEDGE}, ensure_ascii=False),
        encoding="utf-8",
    )
    (summaries / f"{book_key}_final_001.md").write_text("最終要約\n", encoding="utf-8")
    out = root / "book_analysis" / "semantica" / book_key
    out.mkdir(parents=True, exist_ok=True)
    (out / BATCH_STATE_FILENAME).write_text(
        json.dumps(
            {
                "book_key": book_key,
                "next_offset": 2,
                "total_items": 4,
                "complete": False,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return out


def extract_by_text(items, config):
    del config
    entities = [
        {"id": item["text"], "name": item["text"], "type": "Concept"} for item in items
    ]
    relations = []
    if len(items) >= 2:
        relations.append(
            {
                "source": items[0]["text"],
                "target": items[1]["text"],
                "type": "related_to",
            }
        )
    return entities, relations


def ontology(_summary, _config):
    return {"name": "Demo", "classes": [], "properties": []}


def fake_build_graph(entities, relations):
    return {
        "entities": list(entities),
        "relationships": list(relations),
        "metadata": {},
    }


def fake_export_all(out_dir, *, graph, ontology, **kwargs):
    del ontology, kwargs
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "graph.json").write_text(
        json.dumps(graph, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def run_probe(label: str, *, cache=None, cache_bytes=None) -> dict:
    seen: list[str] = []

    def extract(items, config):
        seen.extend(item["text"] for item in items)
        return extract_by_text(items, config)

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        book_key = "ready.ocr"
        out = write_book(root, book_key)
        cache_path = out / EXTRACT_CACHE_FILENAME
        if cache_bytes is not None:
            cache_path.write_bytes(cache_bytes)
        elif isinstance(cache, dict):
            cache_path.write_text(
                json.dumps(cache, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        elif isinstance(cache, str):
            cache_path.write_text(cache, encoding="utf-8")
        cache_present = cache_path.is_file()
        with patch("book_semantica.graph.build_graph", fake_build_graph), patch(
            "book_semantica.graph.detect_conflicts", return_value=[]
        ), patch("book_semantica.pipeline.export_all", fake_export_all):
            try:
                rows = run_batch(
                    repo_root=root,
                    extract_entities_relations=extract,
                    generate_ontology=ontology,
                    book_keys=[book_key],
                    limit=2,
                    offset=0,
                )
                err = None
            except Exception as exc:
                rows = []
                err = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
        row = rows[0] if rows else {}
        cache_ids = []
        covered_end = None
        if (out / EXTRACT_CACHE_FILENAME).is_file():
            try:
                payload = json.loads(
                    (out / EXTRACT_CACHE_FILENAME).read_text(encoding="utf-8")
                )
                if isinstance(payload, dict):
                    cache_ids = [ent["id"] for ent in payload.get("entities") or []]
                    covered_end = payload.get("covered_end")
            except (OSError, json.JSONDecodeError, UnicodeDecodeError):
                payload = None
        else:
            payload = None
        result = {
            "label": label,
            "cache_present_before": cache_present,
            "status": row.get("status"),
            "offset": row.get("offset"),
            "error": row.get("error") or err,
            "seen": list(seen),
            "cache_ids": cache_ids,
            "covered_end": covered_end,
            "first_two": seen[:2] if seen else [],
            "is_ab": seen == ["命題A", "命題B"],
            "is_cd": seen == ["命題C", "命題D"],
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result


def main() -> int:
    results = []
    results.append(run_probe("PROBE4b_missing_cache", cache=None))
    results.append(
        run_probe(
            "PROBE4b_present_cache_AB",
            cache={
                "entities": [
                    {"id": "命題A", "name": "命題A", "type": "Concept"},
                    {"id": "命題B", "name": "命題B", "type": "Concept"},
                ],
                "relations": [],
                "covered_end": 2,
            },
        )
    )
    results.append(run_probe("PROBE4b_corrupt_json", cache="{not json"))
    results.append(run_probe("PROBE4b_json_array", cache="[1, 2]"))
    results.append(run_probe("PROBE4b_empty_object", cache={}))
    results.append(run_probe("PROBE4b_binary_not_utf8", cache_bytes=b"\xff\xfe{not"))
    print("---SUMMARY---")
    for item in results:
        print(
            f"{item['label']}\tstatus={item['status']}\toffset={item['offset']}"
            f"\tseen={item['seen']}\tis_ab={item['is_ab']}\tis_cd={item['is_cd']}"
            f"\terror={item['error']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
