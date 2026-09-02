import sys
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_self_loop_does_not_create_alias_group(self):
        entities = [{"id": "Product Owner", "name": "Product Owner"}]
        relations = [
            {
                "source": "Product Owner",
                "target": "Product Owner",
                "type": "same_as",
            }
        ]
        result = quality.collect_duplicates(entities, relations)
        kinds = {group["kind"] for group in result["groups"]}
        self.assertNotIn("alias", kinds)
        self.assertFalse(result["groups"])


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

    def test_self_same_as_only_does_not_raise(self):
        graph = {
            "relationships": [
                {
                    "source": "Product Owner",
                    "target": "Product Owner",
                    "type": "same_as",
                }
            ]
        }
        quality.assert_artifact_quality(
            owl='<rdfs:label xml:lang="ja">労務</rdfs:label>',
            shacl="sh:datatype xsd:string .",
            duplicates={"groups": []},
            conflicts=[],
            ontology={"classes": [{"name": "LaborAffairs", "label": "労務"}]},
            graph=graph,
        )

    def test_collect_duplicates_and_gate_use_only_iter_alias_pairs(self):
        rels = [{"source": "Labor", "target": "労務", "type": "also_known_as"}]
        with patch.object(quality, "iter_alias_pairs", return_value=[]):
            result = quality.collect_duplicates(
                [{"id": "Labor"}, {"id": "労務"}], rels
            )
            self.assertFalse(
                any(group.get("kind") == "alias" for group in result["groups"])
            )
            quality.assert_artifact_quality(
                owl='<rdfs:label xml:lang="ja">労務</rdfs:label>',
                shacl="sh:datatype xsd:string .",
                duplicates={"groups": []},
                conflicts=[],
                ontology={"classes": [{"name": "LaborAffairs", "label": "労務"}]},
                graph={"relationships": rels},
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


class AliasPairTests(unittest.TestCase):
    def test_empty_and_none_are_not_alias_pairs(self):
        self.assertEqual(list(quality.iter_alias_pairs([])), [])
        self.assertEqual(list(quality.iter_alias_pairs(None)), [])

    def test_self_loop_is_not_an_alias_pair(self):
        rels = [
            {
                "source": "Product Owner",
                "target": "Product Owner",
                "type": "same_as",
            }
        ]
        self.assertEqual(list(quality.iter_alias_pairs(rels)), [])

    def test_distinct_also_known_as_is_an_alias_pair(self):
        rels = [{"source": "Labor", "target": "労務", "type": "also_known_as"}]
        self.assertEqual(list(quality.iter_alias_pairs(rels)), [("Labor", "労務")])

    def test_blank_and_none_endpoints_are_not_alias_pairs(self):
        rels = [
            {"source": "", "target": "労務", "type": "same_as"},
            {"source": "Labor", "target": None, "type": "same_as"},
            {"source": "None", "target": "労務", "type": "same_as"},
        ]
        self.assertEqual(list(quality.iter_alias_pairs(rels)), [])


class IdentityEdgeTests(unittest.TestCase):
    def test_drops_self_loops_of_any_relation_type(self):
        rels = [
            {
                "source": "Product Owner",
                "target": "Product Owner",
                "type": "same_as",
            },
            {"source": "AI", "target": "AI", "type": "is_a"},
            {"source": "Labor", "target": "労務", "type": "also_known_as"},
        ]
        kept = quality.drop_identity_edges(rels)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["source"], "Labor")
        self.assertEqual(kept[0]["target"], "労務")

    def test_strips_before_comparing_endpoints(self):
        rels = [{"source": "AI ", "target": "AI", "type": "related_to"}]
        self.assertEqual(quality.drop_identity_edges(rels), [])

    def test_empty_and_none_relationships_yield_empty(self):
        self.assertEqual(quality.drop_identity_edges([]), [])
        self.assertEqual(quality.drop_identity_edges(None), [])


if __name__ == "__main__":
    unittest.main()
