import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from book_semantica import load_book, provenance, query


class NormalizeKnowledgeTests(unittest.TestCase):
    def test_legacy_strings_become_text_with_null_page(self):
        items = load_book.normalize_knowledge(["旧形式の命題", "  ", ""])
        self.assertEqual(items, [{"text": "旧形式の命題", "page": None}])

    def test_page_dicts_are_kept(self):
        items = load_book.normalize_knowledge(
            [
                {"text": "労務は義務を果たすことである", "page": 12},
                {"text": "空白は捨てる", "page": 3},
            ]
        )
        self.assertEqual(
            items,
            [
                {"text": "労務は義務を果たすことである", "page": 12},
                {"text": "空白は捨てる", "page": 3},
            ],
        )

    def test_mixed_legacy_and_page_items(self):
        items = load_book.normalize_knowledge(
            [
                "旧形式の命題",
                {"text": "新規の命題", "page": 5},
            ]
        )
        self.assertEqual(
            items,
            [
                {"text": "旧形式の命題", "page": None},
                {"text": "新規の命題", "page": 5},
            ],
        )

    def test_invalid_page_becomes_none(self):
        items = load_book.normalize_knowledge([{"text": "頁が壊れている", "page": "x"}])
        self.assertEqual(items, [{"text": "頁が壊れている", "page": None}])


class LoadFromFilesTests(unittest.TestCase):
    def test_load_knowledge_applies_limit_and_normalizes(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            kb = root / "book_analysis" / "knowledge_bases"
            kb.mkdir(parents=True)
            (kb / "demo_knowledge.json").write_text(
                json.dumps(
                    {
                        "knowledge": [
                            "文字列の命題",
                            {"text": "ページ付き", "page": 4},
                            {"text": "三件目", "page": 9},
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            loaded = load_book.load_knowledge("demo", limit=2, repo_root=root)
        self.assertEqual(
            loaded,
            [
                {"text": "文字列の命題", "page": None},
                {"text": "ページ付き", "page": 4},
            ],
        )

    def test_load_summary_picks_latest_final(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            summaries = root / "book_analysis" / "summaries"
            summaries.mkdir(parents=True)
            (summaries / "demo_final_001.md").write_text("古い要約", encoding="utf-8")
            (summaries / "demo_final_002.md").write_text("新しい要約", encoding="utf-8")
            text = load_book.load_summary("demo", repo_root=root)
        self.assertEqual(text, "新しい要約")

    def test_missing_knowledge_raises(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                load_book.load_knowledge("missing", repo_root=Path(tmp))


class ProvenanceStampTests(unittest.TestCase):
    def test_stamps_book_key_always_and_page_when_present(self):
        entity = {"id": "労務", "name": "労務", "type": "Concept"}
        stamped = provenance.stamp_entity(entity, book_key="労務入門.ocr", page=12)
        self.assertEqual(stamped["book_key"], "労務入門.ocr")
        self.assertEqual(stamped["page"], 12)
        self.assertEqual(stamped["metadata"]["book_key"], "労務入門.ocr")
        self.assertEqual(stamped["metadata"]["page"], 12)

    def test_omits_page_when_absent(self):
        entity = {"id": "労務", "name": "労務", "type": "Concept"}
        stamped = provenance.stamp_entity(entity, book_key="労務入門.ocr", page=None)
        self.assertEqual(stamped["book_key"], "労務入門.ocr")
        self.assertIsNone(stamped.get("page"))
        self.assertNotIn("page", stamped.get("metadata", {}))


class ResolveXaiKeyTests(unittest.TestCase):
    def test_prefers_env_key(self):
        import os

        from book_semantica.resolve_xai_key import resolve_token

        old = os.environ.get("XAI_API_KEY")
        os.environ["XAI_API_KEY"] = "from-env-not-a-real-key"
        try:
            self.assertEqual(resolve_token(), "from-env-not-a-real-key")
        finally:
            if old is None:
                os.environ.pop("XAI_API_KEY", None)
            else:
                os.environ["XAI_API_KEY"] = old


class QueryGraphTests(unittest.TestCase):
    def setUp(self):
        self.graph = {
            "entities": [
                {"id": "労務", "name": "労務", "type": "Concept"},
                {"id": "人材マネジメント", "name": "人材マネジメント", "type": "Concept"},
                {"id": "ルール", "name": "ルール", "type": "Element"},
            ],
            "relationships": [
                {
                    "source": "労務",
                    "target": "人材マネジメント",
                    "type": "contrasts_with",
                },
                {"source": "労務", "target": "ルール", "type": "has_element"},
            ],
        }

    def test_neighbors_by_name(self):
        result = query.neighbors(self.graph, "労務")
        names = {item["name"] for item in result["neighbors"]}
        self.assertEqual(names, {"人材マネジメント", "ルール"})

    def test_path_between_names(self):
        result = query.shortest_path(self.graph, "人材マネジメント", "ルール")
        self.assertEqual(result["nodes"], ["人材マネジメント", "労務", "ルール"])


if __name__ == "__main__":
    unittest.main()
