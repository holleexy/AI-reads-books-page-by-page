import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from book_semantica import quality


class OwlLabelTests(unittest.TestCase):
    def test_rdfs_label_uses_japanese_not_english_name(self):
        ontology = {
            "uri": "https://books.local/demo/",
            "name": "DemoOntology",
            "classes": [
                {
                    "name": "LaborAffairs",
                    "label": "労務",
                    "comment": "労働における義務を果たす人事領域",
                    "uri": "https://books.local/demo/LaborAffairs",
                    "parent": "HumanResources",
                },
                {
                    "name": "HumanResources",
                    "label": "人事",
                    "uri": "https://books.local/demo/HumanResources",
                },
            ],
            "properties": [
                {
                    "name": "title",
                    "type": "data",
                    "label": "書名",
                    "range": ["xsd:string"],
                    "domain": ["LaborAffairs"],
                    "uri": "https://books.local/demo/title",
                }
            ],
        }
        owl = quality.render_owl(ontology)
        self.assertIn('<rdfs:label xml:lang="ja">労務</rdfs:label>', owl)
        self.assertNotIn("<rdfs:label>LaborAffairs</rdfs:label>", owl)
        self.assertIn("rdf:about=\"https://books.local/demo/LaborAffairs\"", owl)
        self.assertIn("rdfs:subClassOf", owl)


class ShaclDatatypeTests(unittest.TestCase):
    def test_strips_double_xsd_prefix(self):
        raw = 'sh:datatype xsd:xsd:string ;\nsh:datatype xsd:xsd:boolean .'
        fixed = quality.fix_shacl_datatypes(raw)
        self.assertNotIn("xsd:xsd:", fixed)
        self.assertIn("xsd:string", fixed)
        self.assertIn("xsd:boolean", fixed)

    def test_normalizes_property_range(self):
        self.assertEqual(quality.normalize_datatype("xsd:xsd:string"), "xsd:string")
        self.assertEqual(quality.normalize_datatype("string"), "xsd:string")
        self.assertEqual(quality.normalize_datatype("xsd:string"), "xsd:string")


class DuplicateAliasTests(unittest.TestCase):
    def test_also_known_as_becomes_a_group(self):
        entities = [
            {"id": "Labor", "name": "Labor", "type": "CONCEPT"},
            {"id": "労務", "name": "労務", "type": "CONCEPT"},
            {"id": "勤怠管理", "name": "勤怠管理", "type": "CONCEPT"},
        ]
        relations = [
            {"source": "Labor", "target": "労務", "type": "also_known_as"},
            {"source": "attendance management", "target": "勤怠管理", "type": "translated_as"},
        ]
        result = quality.collect_duplicates(entities, relations)
        keys = {tuple(sorted(group["members"])) for group in result["groups"]}
        self.assertIn(("Labor", "労務"), keys)
        self.assertTrue(result["groups"])

    def test_exact_id_collision_is_a_group(self):
        entities = [
            {"id": "労務", "name": "労務", "definition": "義務"},
            {"id": "労務", "name": "労務", "definition": "守り"},
        ]
        result = quality.collect_duplicates(entities, [])
        self.assertEqual(result["groups"][0]["members"], ["労務"])
        self.assertEqual(result["groups"][0]["count"], 2)


class ConflictFilterTests(unittest.TestCase):
    def test_drops_null_id_confidence_noise(self):
        raw = [
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
        kept = quality.filter_conflicts(raw)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["entity_id"], "労務")


class QualityGateTests(unittest.TestCase):
    def test_raises_on_english_owl_label(self):
        ontology = {
            "classes": [{"name": "LaborAffairs", "label": "労務"}],
        }
        owl = '<owl:Class rdf:about="x"><rdfs:label>LaborAffairs</rdfs:label></owl:Class>'
        with self.assertRaises(quality.QualityError):
            quality.assert_artifact_quality(
                owl=owl,
                shacl="sh:datatype xsd:string .",
                duplicates={"groups": []},
                conflicts=[],
                ontology=ontology,
            )

    def test_raises_on_doubled_xsd(self):
        with self.assertRaises(quality.QualityError):
            quality.assert_artifact_quality(
                owl='<rdfs:label xml:lang="ja">労務</rdfs:label>',
                shacl="sh:datatype xsd:xsd:string .",
                duplicates={"groups": []},
                conflicts=[],
                ontology={"classes": [{"name": "LaborAffairs", "label": "労務"}]},
            )

    def test_raises_on_empty_duplicates_when_alias_exists(self):
        graph = {
            "relationships": [
                {"source": "Labor", "target": "労務", "type": "also_known_as"},
            ]
        }
        with self.assertRaises(quality.QualityError):
            quality.assert_artifact_quality(
                owl='<rdfs:label xml:lang="ja">労務</rdfs:label>',
                shacl="sh:datatype xsd:string .",
                duplicates={"groups": []},
                conflicts=[],
                ontology={"classes": [{"name": "LaborAffairs", "label": "労務"}]},
                graph=graph,
            )

    def test_raises_on_confidence_conflict_noise(self):
        with self.assertRaises(quality.QualityError):
            quality.assert_artifact_quality(
                owl='<rdfs:label xml:lang="ja">労務</rdfs:label>',
                shacl="sh:datatype xsd:string .",
                duplicates={"groups": []},
                conflicts=[
                    {
                        "entity_id": None,
                        "property_name": "confidence",
                        "relationship_id": "None_None_focuses_on",
                    }
                ],
                ontology={"classes": [{"name": "LaborAffairs", "label": "労務"}]},
            )

    def test_merge_keeps_both_exact_id_and_alias_groups(self):
        exact = {
            "pre_merge_count": 2,
            "groups": [{"kind": "exact_id", "members": ["労務"]}],
        }
        alias = quality.collect_duplicates(
            [{"id": "Labor"}, {"id": "労務"}],
            [{"source": "Labor", "target": "労務", "type": "also_known_as"}],
        )
        merged = quality.merge_duplicate_reports(exact, alias)
        kinds = {group["kind"] for group in merged["groups"]}
        self.assertIn("exact_id", kinds)
        self.assertIn("alias", kinds)


if __name__ == "__main__":
    unittest.main()
