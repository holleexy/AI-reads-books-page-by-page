"""Batch discover/skip/resume/manifest. Must not import semantica."""

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from book_semantica.paths import ForbiddenOutputPath, HERMES_GRAPH_PATH


def _write_book(root: Path, book_key: str, knowledge, *, has_graph: bool = False) -> None:
    kb = root / "book_analysis" / "knowledge_bases"
    summaries = root / "book_analysis" / "summaries"
    kb.mkdir(parents=True, exist_ok=True)
    summaries.mkdir(parents=True, exist_ok=True)
    (kb / f"{book_key}_knowledge.json").write_text(
        json.dumps({"knowledge": knowledge}, ensure_ascii=False),
        encoding="utf-8",
    )
    (summaries / f"{book_key}_final_001.md").write_text("最終要約\n", encoding="utf-8")
    if has_graph:
        out = root / "book_analysis" / "semantica" / book_key
        out.mkdir(parents=True, exist_ok=True)
        (out / "graph.json").write_text(
            json.dumps(
                {
                    "entities": [
                        {"id": "done", "name": "済みの命題", "type": "Concept"}
                    ],
                    "relationships": [],
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )


def _two_book_root(tmp: str) -> Path:
    root = Path(tmp)
    _write_book(
        root,
        "ready.ocr",
        [
            {"text": "命題A", "page": 1},
            {"text": "命題B", "page": 2},
            {"text": "命題C", "page": 3},
            {"text": "命題D", "page": 4},
        ],
    )
    _write_book(
        root,
        "done.ocr",
        [{"text": "済みの命題", "page": 1}],
        has_graph=True,
    )
    return root


def _extract_by_text(items, config):
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


def _ontology(_summary, _config):
    return {"name": "Demo", "classes": [], "properties": []}


def _assert_no_semantica_import(path: Path) -> None:
    import ast

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name == "semantica" or name.startswith("semantica."):
                    raise AssertionError(f"{path} imports {name}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            name = node.module
            if name == "semantica" or name.startswith("semantica."):
                raise AssertionError(f"{path} imports {name}")


class NoSemanticaImportTests(unittest.TestCase):
    def test_this_file_does_not_import_semantica(self):
        _assert_no_semantica_import(Path(__file__))

    def test_batch_modules_do_not_import_semantica(self):
        repo = Path(__file__).resolve().parent.parent
        for rel in (
            "book_semantica/batch.py",
            "book_semantica/discover.py",
        ):
            _assert_no_semantica_import(repo / rel)


class DiscoverTests(unittest.TestCase):
    def test_lists_knowledge_plus_summary_and_marks_existing_graph(self):
        from book_semantica.discover import list_ready_books

        with TemporaryDirectory() as tmp:
            root = _two_book_root(tmp)
            _write_book(root, "no_summary.ocr", ["無視"])
            (root / "book_analysis" / "summaries" / "no_summary.ocr_final_001.md").unlink()

            books = list_ready_books(repo_root=root)
            keys = [book.book_key for book in books]
            self.assertEqual(keys, ["done.ocr", "ready.ocr"])
            by_key = {book.book_key: book for book in books}
            self.assertTrue(by_key["done.ocr"].has_graph)
            self.assertFalse(by_key["ready.ocr"].has_graph)
            self.assertEqual(by_key["ready.ocr"].total_items, 4)


class PlanTests(unittest.TestCase):
    def test_plan_marks_graph_as_skip_and_missing_as_pending(self):
        from book_semantica.batch import format_plan, plan_books

        with TemporaryDirectory() as tmp:
            root = _two_book_root(tmp)
            rows = plan_books(repo_root=root)
            by_key = {row["book_key"]: row for row in rows}
            self.assertEqual(by_key["done.ocr"]["status"], "skip")
            self.assertEqual(by_key["ready.ocr"]["status"], "pending")
            text = format_plan(rows)
            self.assertIn("done.ocr", text)
            self.assertIn("skip", text)
            self.assertIn("ready.ocr", text)
            self.assertIn("pending", text)


class SkipTests(unittest.TestCase):
    def test_existing_graph_without_state_is_skip_unless_force(self):
        from book_semantica.discover import list_ready_books, should_skip_book

        with TemporaryDirectory() as tmp:
            root = _two_book_root(tmp)
            books = {book.book_key: book for book in list_ready_books(repo_root=root)}
            self.assertTrue(should_skip_book(books["done.ocr"], force=False))
            self.assertFalse(should_skip_book(books["done.ocr"], force=True))
            self.assertFalse(should_skip_book(books["ready.ocr"], force=False))

    def test_incomplete_state_is_not_skipped(self):
        from book_semantica.discover import list_ready_books, should_skip_book
        from book_semantica.paths import BATCH_STATE_FILENAME

        with TemporaryDirectory() as tmp:
            root = _two_book_root(tmp)
            state_dir = root / "book_analysis" / "semantica" / "done.ocr"
            (state_dir / BATCH_STATE_FILENAME).write_text(
                json.dumps(
                    {"next_offset": 2, "total_items": 10, "complete": False},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            books = {book.book_key: book for book in list_ready_books(repo_root=root)}
            self.assertFalse(should_skip_book(books["done.ocr"], force=False))


class EmptyGraphSkipTests(unittest.TestCase):
    def test_zero_byte_graph_is_not_skip(self):
        from book_semantica.discover import list_ready_books, should_skip_book

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_book(root, "empty.ocr", [{"text": "命題", "page": 1}])
            out = root / "book_analysis" / "semantica" / "empty.ocr"
            out.mkdir(parents=True, exist_ok=True)
            (out / "graph.json").write_bytes(b"")
            books = {book.book_key: book for book in list_ready_books(repo_root=root)}
            self.assertFalse(books["empty.ocr"].has_graph)
            self.assertFalse(should_skip_book(books["empty.ocr"], force=False))

    def test_entity_less_graph_is_not_skip(self):
        from book_semantica.discover import list_ready_books, should_skip_book

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_book(root, "empty.ocr", [{"text": "命題", "page": 1}])
            out = root / "book_analysis" / "semantica" / "empty.ocr"
            out.mkdir(parents=True, exist_ok=True)
            (out / "graph.json").write_text(
                json.dumps({"entities": [], "relationships": []}, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )
            books = {book.book_key: book for book in list_ready_books(repo_root=root)}
            self.assertFalse(books["empty.ocr"].has_graph)
            self.assertFalse(should_skip_book(books["empty.ocr"], force=False))

    def test_real_graph_without_state_is_still_skip(self):
        from book_semantica.discover import list_ready_books, should_skip_book

        with TemporaryDirectory() as tmp:
            root = _two_book_root(tmp)
            books = {book.book_key: book for book in list_ready_books(repo_root=root)}
            self.assertTrue(books["done.ocr"].has_graph)
            self.assertTrue(should_skip_book(books["done.ocr"], force=False))

    def test_empty_graph_is_retried_by_batch_without_force(self):
        from book_semantica.batch import run_batch

        run_calls = []

        def run_book(config, **kwargs):
            run_calls.append(config.book_key)
            return Path("/unused")

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_book(root, "empty.ocr", [{"text": "命題", "page": 1}])
            out = root / "book_analysis" / "semantica" / "empty.ocr"
            out.mkdir(parents=True, exist_ok=True)
            (out / "graph.json").write_text(
                json.dumps({"entities": [], "relationships": []}, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )
            rows = run_batch(
                repo_root=root,
                extract_entities_relations=_extract_by_text,
                generate_ontology=_ontology,
                run_book_fn=run_book,
            )
            self.assertEqual(run_calls, ["empty.ocr"])
            self.assertEqual(rows[0]["status"], "success")


class DryRunTests(unittest.TestCase):
    def test_dry_run_does_not_call_extract_or_run_book(self):
        from book_semantica.batch import run_batch

        extract_calls = []
        run_calls = []

        def extract(items, config):
            extract_calls.append(list(items))
            return [], []

        def run_book(config, **kwargs):
            run_calls.append(config.book_key)
            return Path("/unused")

        with TemporaryDirectory() as tmp:
            root = _two_book_root(tmp)
            rows = run_batch(
                repo_root=root,
                dry_run=True,
                extract_entities_relations=extract,
                generate_ontology=_ontology,
                run_book_fn=run_book,
            )
        self.assertEqual(extract_calls, [])
        self.assertEqual(run_calls, [])
        by_key = {row["book_key"]: row for row in rows}
        self.assertEqual(by_key["done.ocr"]["status"], "skip")
        self.assertEqual(by_key["ready.ocr"]["status"], "pending")


class BatchMockTests(unittest.TestCase):
    def test_batch_runs_only_missing_book_and_writes_manifest(self):
        from book_semantica.batch import run_batch
        from book_semantica.paths import MANIFEST_RELPATH

        run_calls = []

        def run_book(config, **kwargs):
            run_calls.append(config.book_key)
            out = Path(config.repo_root) / "book_analysis" / "semantica" / config.book_key
            out.mkdir(parents=True, exist_ok=True)
            return out

        with TemporaryDirectory() as tmp:
            root = _two_book_root(tmp)
            rows = run_batch(
                repo_root=root,
                extract_entities_relations=_extract_by_text,
                generate_ontology=_ontology,
                run_book_fn=run_book,
            )
            self.assertEqual(run_calls, ["ready.ocr"])
            by_key = {row["book_key"]: row for row in rows}
            self.assertEqual(by_key["done.ocr"]["status"], "skip")
            self.assertEqual(by_key["ready.ocr"]["status"], "success")
            manifest = root / MANIFEST_RELPATH
            self.assertTrue(manifest.is_file())
            recorded = [
                json.loads(line)
                for line in manifest.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            statuses = {row["book_key"]: row["status"] for row in recorded}
            self.assertEqual(statuses["done.ocr"], "skip")
            self.assertEqual(statuses["ready.ocr"], "success")
            success = next(row for row in recorded if row["book_key"] == "ready.ocr")
            self.assertIn("offset", success)
            self.assertIn("timestamp", success)
            self.assertIn("output_dir", success)
            self.assertNotEqual(
                Path(success["output_dir"]).resolve(),
                HERMES_GRAPH_PATH.resolve(),
            )
            self.assertNotIn("hermes", success["output_dir"])


class ResumeCacheTests(unittest.TestCase):
    def test_second_chunk_does_not_reextract_first_slice(self):
        from book_semantica.pipeline import RunConfig, accumulate_extract

        seen = []

        def extract(items, config):
            seen.extend(item["text"] for item in items)
            return _extract_by_text(items, config)

        with TemporaryDirectory() as tmp:
            root = _two_book_root(tmp)
            config = RunConfig(
                book_key="ready.ocr",
                repo_root=root,
                offset=0,
                limit=2,
            )
            first = accumulate_extract(
                config,
                extract_entities_relations=extract,
                generate_ontology=_ontology,
            )
            self.assertEqual(seen, ["命題A", "命題B"])
            self.assertEqual(len(first.entities), 2)
            self.assertEqual(first.state["next_offset"], 2)
            self.assertFalse(first.state["complete"])
            state_path = first.output_dir / "batch_state.json"
            self.assertTrue(state_path.is_file())

            seen.clear()
            config.offset = 2
            second = accumulate_extract(
                config,
                extract_entities_relations=extract,
                generate_ontology=_ontology,
            )
            self.assertEqual(seen, ["命題C", "命題D"])
            self.assertEqual(len(second.entities), 4)
            self.assertEqual({ent["id"] for ent in second.entities}, {"命題A", "命題B", "命題C", "命題D"})
            self.assertEqual(second.state["next_offset"], 4)
            self.assertTrue(second.state["complete"])

    def test_overlapping_offset_does_not_reextract_cached_prefix(self):
        from book_semantica.pipeline import RunConfig, accumulate_extract

        seen = []

        def extract(items, config):
            seen.extend(item["text"] for item in items)
            return _extract_by_text(items, config)

        with TemporaryDirectory() as tmp:
            root = _two_book_root(tmp)
            config = RunConfig(
                book_key="ready.ocr",
                repo_root=root,
                offset=0,
                limit=2,
            )
            accumulate_extract(
                config,
                extract_entities_relations=extract,
                generate_ontology=_ontology,
            )
            seen.clear()
            config.limit = 4
            accumulate_extract(
                config,
                extract_entities_relations=extract,
                generate_ontology=_ontology,
            )
            self.assertEqual(seen, ["命題C", "命題D"])


class MissingCacheResumeTests(unittest.TestCase):
    def test_missing_cache_reextracts_from_start_despite_next_offset(self):
        from book_semantica.paths import BATCH_STATE_FILENAME, EXTRACT_CACHE_FILENAME
        from book_semantica.pipeline import RunConfig, accumulate_extract

        seen = []

        def extract(items, config):
            seen.extend(item["text"] for item in items)
            return _extract_by_text(items, config)

        with TemporaryDirectory() as tmp:
            root = _two_book_root(tmp)
            out = root / "book_analysis" / "semantica" / "ready.ocr"
            out.mkdir(parents=True, exist_ok=True)
            (out / BATCH_STATE_FILENAME).write_text(
                json.dumps(
                    {
                        "book_key": "ready.ocr",
                        "next_offset": 2,
                        "total_items": 4,
                        "complete": False,
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            cache_path = out / EXTRACT_CACHE_FILENAME
            self.assertFalse(cache_path.is_file())
            result = accumulate_extract(
                RunConfig(
                    book_key="ready.ocr",
                    repo_root=root,
                    offset=0,
                    limit=2,
                ),
                extract_entities_relations=extract,
                generate_ontology=_ontology,
            )
            self.assertEqual(seen, ["命題A", "命題B"])
            self.assertEqual(
                [ent["id"] for ent in result.entities],
                ["命題A", "命題B"],
            )
            self.assertTrue(cache_path.is_file())

    def test_run_batch_missing_cache_reextracts_first_slice(self):
        from book_semantica.batch import run_batch
        from book_semantica.paths import BATCH_STATE_FILENAME, EXTRACT_CACHE_FILENAME

        seen = []

        def extract(items, config):
            seen.extend(item["text"] for item in items)
            return _extract_by_text(items, config)

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_book(
                root,
                "ready.ocr",
                [
                    {"text": "命題A", "page": 1},
                    {"text": "命題B", "page": 2},
                    {"text": "命題C", "page": 3},
                    {"text": "命題D", "page": 4},
                ],
            )
            out = root / "book_analysis" / "semantica" / "ready.ocr"
            out.mkdir(parents=True, exist_ok=True)
            (out / BATCH_STATE_FILENAME).write_text(
                json.dumps(
                    {
                        "book_key": "ready.ocr",
                        "next_offset": 2,
                        "total_items": 4,
                        "complete": False,
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            self.assertFalse((out / EXTRACT_CACHE_FILENAME).is_file())
            with patch("book_semantica.graph.build_graph", _fake_build_graph), patch(
                "book_semantica.graph.detect_conflicts", return_value=[]
            ), patch("book_semantica.pipeline.export_all", _fake_export_all):
                rows = run_batch(
                    repo_root=root,
                    extract_entities_relations=extract,
                    generate_ontology=_ontology,
                    book_keys=["ready.ocr"],
                    limit=2,
                    offset=0,
                )
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["status"], "success", rows[0].get("error"))
            self.assertEqual(rows[0]["offset"], 0)
            self.assertIn("命題A", seen)
            self.assertIn("命題B", seen)
            self.assertEqual(seen, ["命題A", "命題B"])
            self.assertNotEqual(seen, ["命題C", "命題D"])
            cache = json.loads((out / EXTRACT_CACHE_FILENAME).read_text(encoding="utf-8"))
            self.assertEqual(
                [ent["id"] for ent in cache.get("entities") or []],
                ["命題A", "命題B"],
            )


class EffectiveOffsetTests(unittest.TestCase):
    def _incomplete_book(self, root: Path, *, cache=None):
        from book_semantica.discover import list_ready_books
        from book_semantica.paths import BATCH_STATE_FILENAME, EXTRACT_CACHE_FILENAME

        _write_book(
            root,
            "ready.ocr",
            [
                {"text": "命題A", "page": 1},
                {"text": "命題B", "page": 2},
                {"text": "命題C", "page": 3},
                {"text": "命題D", "page": 4},
            ],
        )
        out = root / "book_analysis" / "semantica" / "ready.ocr"
        out.mkdir(parents=True, exist_ok=True)
        (out / BATCH_STATE_FILENAME).write_text(
            json.dumps(
                {
                    "book_key": "ready.ocr",
                    "next_offset": 2,
                    "total_items": 4,
                    "complete": False,
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        cache_path = out / EXTRACT_CACHE_FILENAME
        if isinstance(cache, dict):
            cache_path.write_text(
                json.dumps(cache, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        elif isinstance(cache, str):
            cache_path.write_text(cache, encoding="utf-8")
        books = {book.book_key: book for book in list_ready_books(repo_root=root)}
        return books["ready.ocr"]

    def test_missing_cache_uses_cli_offset(self):
        from book_semantica.batch import _effective_offset

        with TemporaryDirectory() as tmp:
            book = self._incomplete_book(Path(tmp), cache=None)
            self.assertEqual(_effective_offset(book, offset=0, force=False), 0)
            self.assertEqual(_effective_offset(book, offset=1, force=False), 1)

    def test_unreadable_cache_uses_cli_offset(self):
        from book_semantica.batch import _effective_offset

        with TemporaryDirectory() as tmp:
            book = self._incomplete_book(Path(tmp), cache="{not json")
            self.assertEqual(_effective_offset(book, offset=0, force=False), 0)
            self.assertEqual(_effective_offset(book, offset=3, force=False), 3)

    def test_present_cache_uses_next_offset(self):
        from book_semantica.batch import _effective_offset

        with TemporaryDirectory() as tmp:
            book = self._incomplete_book(
                Path(tmp),
                cache={
                    "entities": [
                        {"id": "命題A", "name": "命題A", "type": "Concept"},
                        {"id": "命題B", "name": "命題B", "type": "Concept"},
                    ],
                    "relations": [],
                    "covered_end": 2,
                },
            )
            self.assertEqual(_effective_offset(book, offset=0, force=False), 2)
            self.assertEqual(_effective_offset(book, offset=1, force=False), 2)


def _fake_build_graph(entities, relations):
    return {"entities": list(entities), "relationships": list(relations), "metadata": {}}


def _fake_export_all(out_dir, *, graph, ontology, **kwargs):
    del ontology, kwargs
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "graph.json").write_text(
        json.dumps(graph, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


class OcrSuffixOutputDirTests(unittest.TestCase):
    def test_resolve_output_dir_accepts_ocr_directory_name(self):
        from book_semantica.pipeline import RunConfig, _resolve_output_dir

        with TemporaryDirectory() as tmp:
            out = Path(tmp) / "採用入門.ocr"
            resolved = _resolve_output_dir(
                RunConfig(book_key="採用入門.ocr", output_dir=out)
            )
            self.assertEqual(resolved, out)

    def test_resolve_output_dir_rejects_existing_file(self):
        from book_semantica.pipeline import RunConfig, _resolve_output_dir

        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.txt"
            target.write_text("not a directory\n", encoding="utf-8")
            with self.assertRaises(ForbiddenOutputPath) as caught:
                _resolve_output_dir(RunConfig(output_dir=target))
            self.assertIn("must be a directory, not a file", str(caught.exception))

    def test_resolve_output_dir_rejects_hermes_work_json(self):
        from book_semantica.pipeline import RunConfig, _resolve_output_dir

        with self.assertRaises(ForbiddenOutputPath):
            _resolve_output_dir(RunConfig(output_dir=HERMES_GRAPH_PATH))

    def test_run_book_accepts_ocr_suffix_output_dir(self):
        from book_semantica.pipeline import RunConfig, run_book

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_book(
                root,
                "採用入門.ocr",
                [{"text": "命題A", "page": 1}, {"text": "命題B", "page": 2}],
            )
            out = root / "採用入門.ocr"
            config = RunConfig(
                book_key="採用入門.ocr",
                repo_root=root,
                output_dir=out,
                limit=2,
            )
            with patch("book_semantica.graph.build_graph", _fake_build_graph), patch(
                "book_semantica.graph.detect_conflicts", return_value=[]
            ), patch("book_semantica.pipeline.export_all", _fake_export_all):
                result = run_book(
                    config,
                    generate_ontology=_ontology,
                    extract_entities_relations=_extract_by_text,
                )
            self.assertEqual(result, out)
            self.assertTrue((out / "graph.json").is_file())

    def test_run_batch_ocr_book_key_calls_real_run_book(self):
        from book_semantica.batch import run_batch

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_book(
                root,
                "採用入門.ocr",
                [
                    {"text": "命題A", "page": 1},
                    {"text": "命題B", "page": 2},
                    {"text": "命題C", "page": 3},
                    {"text": "命題D", "page": 4},
                ],
            )
            with patch("book_semantica.graph.build_graph", _fake_build_graph), patch(
                "book_semantica.graph.detect_conflicts", return_value=[]
            ), patch("book_semantica.pipeline.export_all", _fake_export_all):
                rows = run_batch(
                    repo_root=root,
                    extract_entities_relations=_extract_by_text,
                    generate_ontology=_ontology,
                    book_keys=["採用入門.ocr"],
                    limit=2,
                )
            by_key = {row["book_key"]: row for row in rows}
            row = by_key["採用入門.ocr"]
            self.assertEqual(row["status"], "success", row.get("error"))
            self.assertNotIn("must be a directory", row.get("error") or "")
            self.assertEqual(row["item_count"], 2)
            self.assertEqual(row["total_items"], 4)
            graph_path = Path(row["output_dir"]) / "graph.json"
            self.assertTrue(graph_path.is_file())


class ManifestHermesTests(unittest.TestCase):
    def test_batch_refuses_hermes_output_dir(self):
        from book_semantica.batch import run_batch

        with TemporaryDirectory() as tmp:
            root = _two_book_root(tmp)
            with self.assertRaises(ForbiddenOutputPath):
                run_batch(
                    repo_root=root,
                    output_dir=HERMES_GRAPH_PATH,
                    dry_run=True,
                    run_book_fn=lambda config, **kwargs: Path("/unused"),
                )


class LoadOffsetTests(unittest.TestCase):
    def test_offset_and_limit_slice_knowledge(self):
        from book_semantica.load_book import load_knowledge

        with TemporaryDirectory() as tmp:
            root = _two_book_root(tmp)
            sliced = load_knowledge(
                "ready.ocr",
                offset=1,
                limit=2,
                repo_root=root,
            )
        self.assertEqual(
            [item["text"] for item in sliced],
            ["命題B", "命題C"],
        )

    def test_limit_zero_means_all_from_offset(self):
        from book_semantica.load_book import load_knowledge

        with TemporaryDirectory() as tmp:
            root = _two_book_root(tmp)
            loaded = load_knowledge(
                "ready.ocr",
                offset=2,
                limit=0,
                repo_root=root,
            )
        self.assertEqual([item["text"] for item in loaded], ["命題C", "命題D"])


class CliPlanTests(unittest.TestCase):
    def test_parse_accepts_plan_batch_offset_force_all_points_dry_run(self):
        from book_semantica.cli import parse_args

        args = parse_args(
            [
                "batch",
                "--offset",
                "80",
                "--limit",
                "0",
                "--force",
                "--all-points",
                "--dry-run",
            ]
        )
        self.assertEqual(args.command, "batch")
        self.assertEqual(args.offset, 80)
        self.assertEqual(args.limit, 0)
        self.assertTrue(args.force)
        self.assertTrue(args.all_points)
        self.assertTrue(args.dry_run)

    def test_run_dry_run_does_not_call_pipeline(self):
        from io import StringIO
        from unittest.mock import patch

        from book_semantica.cli import main

        with patch("book_semantica.pipeline.run_book") as run_book:
            with patch("sys.stdout", new=StringIO()):
                code = main(["run", "--dry-run", "--book-key", "ready.ocr"])
        self.assertEqual(code, 0)
        run_book.assert_not_called()

    def test_plan_main_does_not_need_run_book(self):
        from io import StringIO
        from unittest.mock import patch

        from book_semantica.cli import main

        with TemporaryDirectory() as tmp:
            root = _two_book_root(tmp)
            with patch("sys.stdout", new=StringIO()) as captured:
                code = main(["plan", "--repo-root", str(root)])
            text = captured.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("skip", text)
        self.assertIn("done.ocr", text)
        self.assertIn("pending", text)
        self.assertIn("ready.ocr", text)


if __name__ == "__main__":
    unittest.main()
