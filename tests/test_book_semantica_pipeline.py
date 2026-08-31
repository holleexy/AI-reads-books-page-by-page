import json
import re
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import semantica  # noqa: F401
except ImportError as exc:
    SEMANTICA_IMPORT_ERROR = exc
    semantica = None
else:
    SEMANTICA_IMPORT_ERROR = None


def _write_pilot_inputs(root: Path) -> None:
    kb = root / "book_analysis" / "knowledge_bases"
    summaries = root / "book_analysis" / "summaries"
    kb.mkdir(parents=True)
    summaries.mkdir(parents=True)
    (kb / "労務入門.ocr_knowledge.json").write_text(
        json.dumps(
            {
                "knowledge": [
                    "労務は労働における義務を果たすことである。",
                    {"text": "人材マネジメントは攻めの人事である。", "page": 8},
                    {"text": "労務の構成要素の一つはルールである。", "page": 15},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (summaries / "労務入門.ocr_final_001.md").write_text(
        "労務は守りの人事であり、人材マネジメントは攻めの人事である。\n",
        encoding="utf-8",
    )


def _fake_ontology(summary: str, config) -> dict:
    del summary, config
    base = "https://books.local/労務入門.ocr/"
    return {
        "name": "RomuOntology",
        "uri": base,
        "version": "1.0",
        "classes": [
            {
                "name": "労務",
                "label": "労務",
                "comment": "労働における義務を果たす人事領域",
                "uri": f"{base}労務",
                "parent": None,
            },
            {
                "name": "人材マネジメント",
                "label": "人材マネジメント",
                "comment": "才能へ投資する人事領域",
                "uri": f"{base}人材マネジメント",
                "parent": None,
            },
        ],
        "properties": [
            {
                "name": "contrastsWith",
                "type": "object",
                "domain": ["労務"],
                "range": ["人材マネジメント"],
                "label": "対比する",
                "uri": f"{base}contrastsWith",
            }
        ],
    }


def _fake_extract(items, config):
    from book_semantica.provenance import stamp_entity, stamp_relation

    book_key = config.book_key
    entities = [
        stamp_entity(
            {
                "id": "労務",
                "name": "労務",
                "text": "労務",
                "type": "Concept",
                "definition": "労働における義務を果たすこと",
            },
            book_key=book_key,
            page=3,
        ),
        stamp_entity(
            {
                "id": "人材マネジメント",
                "name": "人材マネジメント",
                "text": "人材マネジメント",
                "type": "Concept",
                "definition": "攻めの人事",
            },
            book_key=book_key,
            page=items[1].get("page") if len(items) > 1 else None,
        ),
        stamp_entity(
            {
                "id": "ルール",
                "name": "ルール",
                "text": "ルール",
                "type": "Element",
                "definition": "労務の構成要素",
            },
            book_key=book_key,
            page=items[2].get("page") if len(items) > 2 else None,
        ),
        stamp_entity(
            {
                "id": "労務",
                "name": "労務",
                "text": "労務",
                "type": "Concept",
                "definition": "守りの人事",
            },
            book_key=book_key,
            page=None,
        ),
    ]
    relations = [
        stamp_relation(
            {
                "source": "労務",
                "target": "人材マネジメント",
                "type": "contrasts_with",
            },
            book_key=book_key,
            page=items[1].get("page") if len(items) > 1 else None,
        ),
        stamp_relation(
            {
                "source": "労務",
                "target": "ルール",
                "type": "has_element",
            },
            book_key=book_key,
            page=items[2].get("page") if len(items) > 2 else None,
        ),
    ]
    return entities, relations


def _owl_class_iris(text: str) -> list[str]:
    return [
        match
        for match in re.findall(r'<owl:Class[^>]*rdf:about="([^"]*)"', text)
        if match.strip()
    ]


@unittest.skipUnless(
    semantica is not None,
    f"semantica is not importable in this interpreter: {SEMANTICA_IMPORT_ERROR}",
)
class MockedPipelineTests(unittest.TestCase):
    def test_mocked_pipeline_writes_required_artifacts(self):
        from book_semantica.paths import HERMES_GRAPH_PATH, book_output_dir
        from book_semantica.pipeline import RunConfig, run_book
        from book_semantica.query import neighbors

        hermes_mtime = None
        if HERMES_GRAPH_PATH.exists():
            hermes_mtime = HERMES_GRAPH_PATH.stat().st_mtime

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_pilot_inputs(root)
            config = RunConfig(
                book_key="労務入門.ocr",
                limit=3,
                repo_root=root,
            )
            out_dir = run_book(
                config,
                generate_ontology=_fake_ontology,
                extract_entities_relations=_fake_extract,
            )
            expected = book_output_dir("労務入門.ocr", repo_root=root)
            self.assertEqual(out_dir, expected)
            for name in (
                "graph.json",
                "ontology.json",
                "ontology.owl",
                "shapes.ttl",
                "graph.html",
                "duplicates.json",
                "conflicts.json",
                "provenance.ttl",
            ):
                path = out_dir / name
                self.assertTrue(path.is_file(), f"missing {name}")
                self.assertGreater(path.stat().st_size, 0, f"empty {name}")

            graph = json.loads((out_dir / "graph.json").read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(graph.get("entities") or []), 1)
            self.assertGreaterEqual(len(graph.get("relationships") or []), 1)
            self.assertNotIn("ner_method", graph.get("metadata") or {})
            romu = None
            for entity in graph["entities"]:
                self.assertEqual(
                    entity.get("book_key")
                    or entity.get("metadata", {}).get("book_key"),
                    "労務入門.ocr",
                )
                if (entity.get("id") or entity.get("name")) == "労務":
                    romu = entity
            self.assertIsNotNone(romu)
            romu_page = romu.get("page")
            if romu_page is None:
                romu_page = (romu.get("metadata") or {}).get("page")
            self.assertEqual(romu_page, 3)

            owl = (out_dir / "ontology.owl").read_text(encoding="utf-8")
            iris = _owl_class_iris(owl)
            self.assertGreaterEqual(len(iris), 1, f"no non-empty owl:Class rdf:about in {owl}")
            self.assertTrue(all(iri.strip() for iri in iris))
            self.assertNotIn('rdf:about=""', owl)
            self.assertIn('xml:lang="ja">労務</rdfs:label>', owl)
            self.assertNotIn("<rdfs:label>LaborAffairs</rdfs:label>", owl)
            shacl = (out_dir / "shapes.ttl").read_text(encoding="utf-8")
            self.assertTrue("sh:" in shacl or "NodeShape" in shacl)
            self.assertNotIn("xsd:xsd:", shacl)

            dups = json.loads((out_dir / "duplicates.json").read_text(encoding="utf-8"))
            self.assertTrue(dups.get("groups"), "duplicates.json must record the two 労務 mentions")

            prov = (out_dir / "provenance.ttl").read_text(encoding="utf-8")
            self.assertIn("労務入門.ocr", prov)
            self.assertIn("book_key", prov)
            self.assertTrue("3" in prov or "8" in prov or "15" in prov)

            conflicts = json.loads((out_dir / "conflicts.json").read_text(encoding="utf-8"))
            self.assertTrue(conflicts, "conflicts.json must not be empty for disagreeing definitions")

            html = (out_dir / "graph.html").read_text(encoding="utf-8")
            self.assertIn("<html", html.lower())

            neighbor_result = neighbors(graph, "労務")
            self.assertGreaterEqual(len(neighbor_result["neighbors"]), 1)

            with self.assertRaises(Exception):
                from book_semantica.paths import assert_safe_output_path

                assert_safe_output_path(HERMES_GRAPH_PATH)

        if hermes_mtime is not None:
            self.assertEqual(HERMES_GRAPH_PATH.stat().st_mtime, hermes_mtime)

    def test_pipeline_refuses_hermes_output_override(self):
        from book_semantica.paths import ForbiddenOutputPath, HERMES_GRAPH_PATH
        from book_semantica.pipeline import RunConfig, run_book

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_pilot_inputs(root)
            config = RunConfig(
                book_key="労務入門.ocr",
                limit=1,
                repo_root=root,
                output_dir=HERMES_GRAPH_PATH,
            )
            with self.assertRaises(ForbiddenOutputPath):
                run_book(
                    config,
                    generate_ontology=_fake_ontology,
                    extract_entities_relations=_fake_extract,
                )

    def test_run_book_accepts_ocr_suffix_output_dir(self):
        from book_semantica.pipeline import RunConfig, _resolve_output_dir, run_book

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            kb = root / "book_analysis" / "knowledge_bases"
            summaries = root / "book_analysis" / "summaries"
            kb.mkdir(parents=True)
            summaries.mkdir(parents=True)
            (kb / "採用入門.ocr_knowledge.json").write_text(
                json.dumps(
                    {
                        "knowledge": [
                            "採用は人と組織を結びつけることである。",
                            {"text": "母集団形成は採用の起点である。", "page": 4},
                            {"text": "選考は基準を揃えることである。", "page": 9},
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (summaries / "採用入門.ocr_final_001.md").write_text(
                "採用は人と組織を結びつける。\n",
                encoding="utf-8",
            )
            out = root / "採用入門.ocr"
            config = RunConfig(
                book_key="採用入門.ocr",
                limit=3,
                repo_root=root,
                output_dir=out,
            )
            self.assertEqual(_resolve_output_dir(config), out)
            result = run_book(
                config,
                generate_ontology=_fake_ontology,
                extract_entities_relations=_fake_extract,
            )
            self.assertEqual(result, out)
            graph = json.loads((out / "graph.json").read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(graph.get("entities") or []), 1)

    def test_run_batch_ocr_key_succeeds_without_replacing_run_book(self):
        from book_semantica.batch import run_batch

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            kb = root / "book_analysis" / "knowledge_bases"
            summaries = root / "book_analysis" / "summaries"
            kb.mkdir(parents=True)
            summaries.mkdir(parents=True)
            (kb / "採用入門.ocr_knowledge.json").write_text(
                json.dumps(
                    {
                        "knowledge": [
                            "採用は人と組織を結びつけることである。",
                            {"text": "母集団形成は採用の起点である。", "page": 4},
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (summaries / "採用入門.ocr_final_001.md").write_text(
                "採用は人と組織を結びつける。\n",
                encoding="utf-8",
            )
            rows = run_batch(
                repo_root=root,
                extract_entities_relations=_fake_extract,
                generate_ontology=_fake_ontology,
                book_keys=["採用入門.ocr"],
                limit=2,
            )
            row = {item["book_key"]: item for item in rows}["採用入門.ocr"]
            self.assertEqual(row["status"], "success", row.get("error"))
            self.assertNotIn("must be a directory", row.get("error") or "")
            self.assertEqual(row["item_count"], 2)

    def test_value_conflicts_are_detected(self):
        from book_semantica.graph import detect_conflicts

        entities = [
            {
                "id": "労務",
                "name": "労務",
                "definition": "労働における義務を果たすこと",
                "book_key": "労務入門.ocr",
            },
            {
                "id": "労務",
                "name": "労務",
                "definition": "守りの人事",
                "book_key": "労務入門.ocr",
            },
        ]
        found = detect_conflicts(entities, [])
        self.assertTrue(found)
        blob = json.dumps(found, ensure_ascii=False)
        self.assertIn("労務", blob)

    def test_empty_llm_ner_skips_relations_without_pattern_fallback(self):
        from book_semantica.extract import extract_entities_relations
        from book_semantica.pipeline import RunConfig

        rel_calls = []

        def empty_ner(*args, **kwargs):
            return []

        def rel_should_not_run(*args, **kwargs):
            rel_calls.append(True)
            raise AssertionError("relation LLM must not run without entities")

        with patch(
            "semantica.semantic_extract.methods.get_entity_method",
            return_value=empty_ner,
        ), patch(
            "semantica.semantic_extract.methods.get_relation_method",
            return_value=rel_should_not_run,
        ):
            ents, rels, used = extract_entities_relations(
                [{"text": "Steve Jobs founded Apple Inc.", "page": 1}],
                RunConfig(book_key="demo"),
            )
        self.assertEqual(ents, [])
        self.assertEqual(rels, [])
        self.assertEqual(used["ner_method"], "llm")
        self.assertEqual(rel_calls, [])

    def test_llm_failure_does_not_use_english_pattern_ner(self):
        from book_semantica.extract import LLMExtractionError, extract_entities_relations
        from book_semantica.pipeline import RunConfig

        def boom(*args, **kwargs):
            raise RuntimeError("simulated xAI failure")

        english = (
            "Steve Jobs founded Apple Inc. in California City in 1976."
        )
        with patch(
            "semantica.semantic_extract.methods.get_entity_method",
            return_value=boom,
        ):
            with self.assertRaises(LLMExtractionError):
                extract_entities_relations(
                    [{"text": english, "page": 1}],
                    RunConfig(book_key="demo"),
                )


if __name__ == "__main__":
    unittest.main()
