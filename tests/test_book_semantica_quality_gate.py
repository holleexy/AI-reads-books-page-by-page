"""Export must refuse the four quality bugs even if callers skip the fixes."""

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from book_semantica import quality
from book_semantica.export_artifacts import (
    export_all,
    render_shacl,
    repair_export,
)
from book_semantica.paths import REPO_ROOT

LIVE_DIR = REPO_ROOT / "book_analysis" / "semantica" / "労務入門.ocr"
EXPORT_SOURCE = REPO_ROOT / "book_semantica" / "export_artifacts.py"

_ONTOLOGY = {
    "classes": [
        {
            "name": "LaborAffairs",
            "label": "労務",
            "comment": "労働における義務を果たす人事領域",
        }
    ],
    "properties": [
        {
            "name": "title",
            "type": "data",
            "label": "書名",
            "range": ["xsd:xsd:string"],
        }
    ],
}
_GRAPH = {
    "entities": [
        {"id": "Labor", "name": "Labor", "book_key": "demo"},
        {"id": "労務", "name": "労務", "book_key": "demo", "page": 3},
    ],
    "relationships": [
        {"source": "Labor", "target": "労務", "type": "also_known_as"},
    ],
}
_NOISE_CONFLICTS = [
    {
        "entity_id": None,
        "property_name": "confidence",
        "relationship_id": "None_None_focuses_on",
        "conflict_type": "relationship_conflict",
        "conflicting_values": [0.95, 0.88],
    },
    {
        "entity_id": "労務",
        "property_name": "definition",
        "conflict_type": "value_conflict",
        "conflicting_values": ["義務", "守り"],
    },
]


class SourceInvariantTests(unittest.TestCase):
    def test_export_does_not_use_owl_exporter_or_english_fallback(self):
        text = EXPORT_SOURCE.read_text(encoding="utf-8")
        self.assertNotIn("import OWLExporter", text)
        self.assertNotRegex(text, r"\bOWLExporter\s*\(")
        self.assertNotIn("_write_owl_fallback", text)
        self.assertIn("render_owl", text)
        self.assertIn("assert_artifact_quality", text)
        self.assertIn("sanitize_export_payload", text)


class ExportSanitizationTests(unittest.TestCase):
    def test_export_all_fills_aliases_filters_noise_and_writes_japanese_owl(self):
        with TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            export_all(
                out_dir,
                graph=_GRAPH,
                ontology=_ONTOLOGY,
                duplicates={"groups": []},
                conflicts=list(_NOISE_CONFLICTS),
                book_key="demo",
            )
            owl = (out_dir / "ontology.owl").read_text(encoding="utf-8")
            shacl = (out_dir / "shapes.ttl").read_text(encoding="utf-8")
            dups = json.loads((out_dir / "duplicates.json").read_text(encoding="utf-8"))
            conflicts = json.loads(
                (out_dir / "conflicts.json").read_text(encoding="utf-8")
            )
            self.assertIn('xml:lang="ja">労務</rdfs:label>', owl)
            self.assertNotIn("<rdfs:label>LaborAffairs</rdfs:label>", owl)
            self.assertNotIn("xsd:xsd:", shacl)
            members = {tuple(sorted(group["members"])) for group in dups["groups"]}
            self.assertIn(("Labor", "労務"), members)
            self.assertEqual(len(conflicts), 1)
            self.assertEqual(conflicts[0]["entity_id"], "労務")

    def test_render_shacl_collapses_generator_double_prefix(self):
        with patch(
            "book_semantica.export_artifacts._shacl_from_generator",
            return_value="sh:datatype xsd:xsd:string .\n",
        ):
            text = render_shacl(_ONTOLOGY, book_key="demo")
        self.assertNotIn("xsd:xsd:", text)
        self.assertIn("xsd:string", text)

    def test_repair_export_does_not_drop_alias_groups(self):
        with TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            out_dir.mkdir()
            (out_dir / "duplicates.json").write_text(
                json.dumps({"groups": []}), encoding="utf-8"
            )
            repair_export(
                out_dir,
                graph=_GRAPH,
                ontology=_ONTOLOGY,
                book_key="demo",
                conflicts=list(_NOISE_CONFLICTS),
            )
            dups = json.loads((out_dir / "duplicates.json").read_text(encoding="utf-8"))
            conflicts = json.loads(
                (out_dir / "conflicts.json").read_text(encoding="utf-8")
            )
            owl = (out_dir / "ontology.owl").read_text(encoding="utf-8")
            self.assertTrue(dups["groups"])
            self.assertEqual(len(conflicts), 1)
            self.assertIn("労務", owl)

    def test_repair_export_strips_identity_edges_from_graph_json(self):
        graph = {
            "entities": list(_GRAPH["entities"]),
            "relationships": [
                {
                    "source": "Product Owner",
                    "target": "Product Owner",
                    "type": "same_as",
                },
                {"source": "Labor", "target": "労務", "type": "also_known_as"},
                {"source": "AI", "target": "AI", "type": "is_a"},
            ],
        }
        with TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            out_dir.mkdir()
            repair_export(
                out_dir,
                graph=graph,
                ontology=_ONTOLOGY,
                book_key="demo",
                conflicts=[],
            )
            written = json.loads((out_dir / "graph.json").read_text(encoding="utf-8"))
            rels = written.get("relationships") or []
            self.assertEqual(len(rels), 1)
            self.assertEqual(rels[0]["source"], "Labor")
            self.assertEqual(rels[0]["target"], "労務")
            for rel in rels:
                src = str(rel.get("source") or "").strip()
                tgt = str(rel.get("target") or "").strip()
                self.assertNotEqual(src, tgt)


@unittest.skipUnless(
    (LIVE_DIR / "ontology.owl").is_file() and (LIVE_DIR / "graph.json").is_file(),
    "no live 労務入門 artifacts",
)
class LiveArtifactGateTests(unittest.TestCase):
    def test_live_artifacts_pass_quality_gate(self):
        ontology = json.loads((LIVE_DIR / "ontology.json").read_text(encoding="utf-8"))
        graph = json.loads((LIVE_DIR / "graph.json").read_text(encoding="utf-8"))
        duplicates = json.loads(
            (LIVE_DIR / "duplicates.json").read_text(encoding="utf-8")
        )
        conflicts = json.loads((LIVE_DIR / "conflicts.json").read_text(encoding="utf-8"))
        owl = (LIVE_DIR / "ontology.owl").read_text(encoding="utf-8")
        shacl = (LIVE_DIR / "shapes.ttl").read_text(encoding="utf-8")
        quality.assert_artifact_quality(
            owl=owl,
            shacl=shacl,
            duplicates=duplicates,
            conflicts=conflicts,
            ontology=ontology,
            graph=graph,
        )


if __name__ == "__main__":
    unittest.main()
