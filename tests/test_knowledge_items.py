import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import read_books


class KnowledgeItemTests(unittest.TestCase):
    def test_new_points_carry_one_based_page(self):
        items = read_books.attach_page(["労務は義務を果たすことである"], page_num=0)
        self.assertEqual(
            items,
            [{"text": "労務は義務を果たすことである", "page": 1}],
        )

    def test_load_wraps_legacy_strings_with_null_page(self):
        with TemporaryDirectory() as tmp:
            config = read_books.BookConfig(pdf_path=Path(tmp) / "book.pdf")
            config.base_dir = Path(tmp)
            config.knowledge_dir.mkdir(parents=True)
            config.knowledge_file.write_text(
                json.dumps({"knowledge": ["旧形式の命題"]}, ensure_ascii=False),
                encoding="utf-8",
            )
            loaded = read_books.load_existing_knowledge(config)
        self.assertEqual(loaded, [{"text": "旧形式の命題", "page": None}])

    def test_analyze_joins_text_not_dicts(self):
        texts = read_books.knowledge_texts(
            [
                {"text": "労務は守りの人事である", "page": 3},
                {"text": "人材マネジメントは攻めの人事である", "page": 4},
            ]
        )
        self.assertEqual(
            texts,
            ["労務は守りの人事である", "人材マネジメントは攻めの人事である"],
        )

    def test_save_roundtrip_keeps_page(self):
        with TemporaryDirectory() as tmp:
            config = read_books.BookConfig(pdf_path=Path(tmp) / "book.pdf")
            config.base_dir = Path(tmp)
            config.knowledge_dir.mkdir(parents=True)
            items = [{"text": "労務は義務を果たすことである", "page": 12}]
            read_books.save_knowledge_base(items, config)
            loaded = read_books.load_existing_knowledge(config)
            raw = json.loads(config.knowledge_file.read_text(encoding="utf-8"))
        self.assertEqual(loaded, items)
        self.assertEqual(
            raw["knowledge"],
            [{"text": "労務は義務を果たすことである", "page": 12}],
        )

    def test_resume_mixes_legacy_null_with_new_pages(self):
        mixed = read_books.normalize_knowledge(
            [
                "旧形式の命題",
                {"text": "新規の命題", "page": 5},
            ]
        )
        self.assertEqual(
            mixed,
            [
                {"text": "旧形式の命題", "page": None},
                {"text": "新規の命題", "page": 5},
            ],
        )


if __name__ == "__main__":
    unittest.main()
