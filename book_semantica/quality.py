"""Quality fixes for OWL labels, SHACL datatypes, duplicates, and conflicts.

Semantica's OWLExporter puts class `name` into rdfs:label, so Japanese `label`
never reaches OWL. SHACLGenerator prefixes `xsd:` onto values that already
have it. DuplicateDetector ignores `also_known_as` / `translated_as` edges.
ConflictDetector emits null-id confidence noise on relationships.
"""

from __future__ import annotations

import re
from typing import Any
from xml.sax.saxutils import escape

ALIAS_RELATIONS = frozenset(
    {
        "also_known_as",
        "translated_as",
        "same_as",
        "alias_of",
        "sameAs",
        "alsoKnownAs",
        "translatedAs",
    }
)
XSD_TYPES = frozenset(
    {
        "string",
        "boolean",
        "integer",
        "decimal",
        "float",
        "double",
        "date",
        "dateTime",
        "anyURI",
    }
)


def _has_cjk(text: str) -> bool:
    return any("\u3040" <= ch <= "\u30ff" or "\u4e00" <= ch <= "\u9fff" for ch in text)


def display_label(item: dict, fallback: str = "") -> str:
    label = str(item.get("label") or "").strip()
    if label:
        return label
    name = str(item.get("name") or fallback or "").strip()
    return name


def normalize_datatype(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return raw
    lowered = raw.lower()
    while lowered.startswith("xsd:"):
        raw = raw[4:]
        lowered = raw.lower()
    if lowered in XSD_TYPES or raw.lower() in XSD_TYPES:
        return f"xsd:{raw.split(':')[-1]}"
    return value


def fix_shacl_datatypes(text: str) -> str:
    return re.sub(r"xsd:(?:xsd:)+", "xsd:", text)


def _class_uri_map(ontology: dict) -> dict[str, str]:
    mapping: dict[str, str] = {}
    base = str(ontology.get("uri") or "https://books.local/ns/")
    if not base.endswith(("/", "#")):
        base += "/"
    for cls in ontology.get("classes") or []:
        name = str(cls.get("name") or "")
        uri = str(cls.get("uri") or "") or (f"{base}{name}" if name else "")
        if name:
            mapping[name] = uri
        label = str(cls.get("label") or "")
        if label:
            mapping[label] = uri
    return mapping


def _resolve_class_ref(ref: str, mapping: dict[str, str], base: str) -> str:
    text = str(ref or "").strip()
    if not text:
        return text
    if text.startswith("http://") or text.startswith("https://"):
        return text
    if text in mapping:
        return mapping[text]
    if not base.endswith(("/", "#")):
        base += "/"
    return f"{base}{text}"


def render_owl(ontology: dict) -> str:
    """OWL/XML that uses Japanese label for rdfs:label, name only in the IRI."""
    uri = str(ontology.get("uri") or "https://books.local/ns/")
    name = str(ontology.get("name") or "Ontology")
    version = str(ontology.get("version") or "1.0")
    mapping = _class_uri_map(ontology)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"',
        '         xmlns:owl="http://www.w3.org/2002/07/owl#"',
        '         xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"',
        '         xmlns:xsd="http://www.w3.org/2001/XMLSchema#">',
        "",
        f'  <owl:Ontology rdf:about="{escape(uri)}">',
        f"    <rdfs:label>{escape(name)}</rdfs:label>",
        f"    <owl:versionInfo>{escape(version)}</owl:versionInfo>",
        "  </owl:Ontology>",
        "",
    ]
    for cls in ontology.get("classes") or []:
        class_name = str(cls.get("name") or "Class")
        class_uri = str(cls.get("uri") or mapping.get(class_name) or f"{uri}{class_name}")
        label = display_label(cls, class_name)
        lang = ' xml:lang="ja"' if _has_cjk(label) else ""
        lines.append(f'  <owl:Class rdf:about="{escape(class_uri)}">')
        lines.append(f"    <rdfs:label{lang}>{escape(label)}</rdfs:label>")
        comment = str(cls.get("comment") or "").strip()
        if comment:
            comment_lang = ' xml:lang="ja"' if _has_cjk(comment) else ""
            lines.append(
                f"    <rdfs:comment{comment_lang}>{escape(comment)}</rdfs:comment>"
            )
        parent = cls.get("parent") or cls.get("subClassOf")
        if parent:
            parent_uri = _resolve_class_ref(str(parent), mapping, uri)
            lines.append(
                f'    <rdfs:subClassOf rdf:resource="{escape(parent_uri)}"/>'
            )
        lines.append("  </owl:Class>")
        lines.append("")

    for prop in ontology.get("properties") or []:
        prop_name = str(prop.get("name") or "property")
        prop_uri = str(prop.get("uri") or f"{uri}{prop_name}")
        label = display_label(prop, prop_name)
        lang = ' xml:lang="ja"' if _has_cjk(label) else ""
        kind = str(prop.get("type") or "object").lower()
        tag = "DatatypeProperty" if kind in {"data", "datatype", "literal"} else "ObjectProperty"
        lines.append(f'  <owl:{tag} rdf:about="{escape(prop_uri)}">')
        lines.append(f"    <rdfs:label{lang}>{escape(label)}</rdfs:label>")
        comment = str(prop.get("comment") or "").strip()
        if comment:
            comment_lang = ' xml:lang="ja"' if _has_cjk(comment) else ""
            lines.append(
                f"    <rdfs:comment{comment_lang}>{escape(comment)}</rdfs:comment>"
            )
        for domain in _as_list(prop.get("domain")):
            domain_uri = _resolve_class_ref(str(domain), mapping, uri)
            lines.append(f'    <rdfs:domain rdf:resource="{escape(domain_uri)}"/>')
        for rng in _as_list(prop.get("range")):
            rng_text = str(rng)
            datatype = normalize_datatype(rng_text)
            if datatype.startswith("xsd:"):
                lines.append(
                    f'    <rdfs:range rdf:resource="http://www.w3.org/2001/XMLSchema#{datatype[4:]}"/>'
                )
            else:
                range_uri = _resolve_class_ref(rng_text, mapping, uri)
                lines.append(f'    <rdfs:range rdf:resource="{escape(range_uri)}"/>')
        lines.append(f"  </owl:{tag}>")
        lines.append("")

    lines.append("</rdf:RDF>")
    return "\n".join(lines) + "\n"


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _member_id(entity: dict) -> str:
    return str(
        entity.get("id")
        or entity.get("entity_id")
        or entity.get("name")
        or entity.get("text")
        or ""
    ).strip()


def _union_find_groups(pairs: list[tuple[str, str]]) -> list[list[str]]:
    parent: dict[str, str] = {}

    def find(node: str) -> str:
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: str, right: str) -> None:
        root_l, root_r = find(left), find(right)
        if root_l != root_r:
            parent[root_r] = root_l

    for left, right in pairs:
        if left and right:
            union(left, right)
    buckets: dict[str, list[str]] = {}
    for node in parent:
        buckets.setdefault(find(node), []).append(node)
    return [sorted(set(members)) for members in buckets.values() if len(set(members)) > 1]


def collect_duplicates(entities: list[dict], relationships: list[dict] | None = None) -> dict[str, Any]:
    """Exact-id collisions plus alias/translation edges."""
    groups: list[dict[str, Any]] = []
    by_id: dict[str, list[dict]] = {}
    for entity in entities or []:
        key = _member_id(entity)
        if key:
            by_id.setdefault(key, []).append(entity)
    for key, items in by_id.items():
        if len(items) > 1:
            groups.append(
                {
                    "kind": "exact_id",
                    "members": [key],
                    "count": len(items),
                    "pages": [
                        item.get("page")
                        or (item.get("metadata") or {}).get("page")
                        for item in items
                    ],
                }
            )

    alias_pairs: list[tuple[str, str]] = []
    for rel in relationships or []:
        rel_type = str(rel.get("type") or rel.get("predicate") or "")
        if rel_type not in ALIAS_RELATIONS:
            continue
        src = str(rel.get("source") or rel.get("subject") or "").strip()
        tgt = str(rel.get("target") or rel.get("object") or "").strip()
        if src and tgt and src != "None" and tgt != "None":
            alias_pairs.append((src, tgt))
    for members in _union_find_groups(alias_pairs):
        groups.append(
            {
                "kind": "alias",
                "members": members,
                "count": len(members),
                "relation": "also_known_as",
            }
        )
    return {
        "pre_merge_count": len(entities or []),
        "groups": groups,
        "candidates": [
            {"kind": group["kind"], "members": group["members"]}
            for group in groups
        ],
    }


def filter_conflicts(conflicts: list[dict] | None) -> list[dict]:
    """Drop null-endpoint confidence noise. Keep real value disagreements."""
    kept: list[dict] = []
    for item in conflicts or []:
        if not isinstance(item, dict):
            kept.append(item)
            continue
        entity_id = item.get("entity_id")
        rel_id = str(item.get("relationship_id") or "")
        prop = str(item.get("property_name") or "")
        if prop == "confidence":
            continue
        if entity_id in {None, "", "None"} and (
            rel_id.startswith("None_None") or "None_None" in rel_id
        ):
            continue
        if entity_id in {None, "", "None"} and not rel_id:
            continue
        kept.append(item)
    return kept


class QualityError(ValueError):
    """Export artifacts violated a locked quality rule."""


def merge_duplicate_reports(*reports: dict | None) -> dict[str, Any]:
    groups: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    pre_merge = 0
    for report in reports:
        if not report:
            continue
        pre_merge = max(pre_merge, int(report.get("pre_merge_count") or 0))
        for group in report.get("groups") or []:
            key = (group.get("kind"), tuple(group.get("members") or []))
            if key in seen:
                continue
            seen.add(key)
            groups.append(group)
    return {
        "pre_merge_count": pre_merge,
        "groups": groups,
        "candidates": [
            {"kind": group.get("kind"), "members": group.get("members")}
            for group in groups
        ],
    }


def assert_artifact_quality(
    *,
    owl: str,
    shacl: str,
    duplicates: dict | None,
    conflicts: list | None,
    ontology: dict,
    graph: dict | None = None,
) -> None:
    """Fail the run if the four locked quality bugs reappear."""
    if "xsd:xsd:" in shacl:
        raise QualityError("SHACL datatype doubled (xsd:xsd:); fix_shacl_datatypes was skipped")

    for cls in ontology.get("classes") or []:
        label = str(cls.get("label") or "").strip()
        name = str(cls.get("name") or "").strip()
        if label and _has_cjk(label):
            if f">{label}</rdfs:label>" not in owl:
                raise QualityError(
                    f"OWL rdfs:label missing Japanese {label!r} (name={name!r})"
                )
            if name and name != label and f"<rdfs:label>{name}</rdfs:label>" in owl:
                raise QualityError(
                    f"OWL rdfs:label used English name {name!r} instead of {label!r}"
                )

    for item in conflicts or []:
        if not isinstance(item, dict):
            continue
        entity_id = item.get("entity_id")
        prop = str(item.get("property_name") or "")
        rel_id = str(item.get("relationship_id") or "")
        if prop == "confidence":
            raise QualityError("conflicts.json still has confidence noise")
        if entity_id in {None, "", "None"} and "None_None" in rel_id:
            raise QualityError("conflicts.json still has null-id relationship noise")

    groups = (duplicates or {}).get("groups") or []
    relations = (graph or {}).get("relationships") or []
    alias_pairs = []
    for rel in relations:
        rel_type = str(rel.get("type") or rel.get("predicate") or "")
        if rel_type not in ALIAS_RELATIONS:
            continue
        src = str(rel.get("source") or "").strip()
        tgt = str(rel.get("target") or "").strip()
        if src and tgt and src != "None" and tgt != "None":
            alias_pairs.append(frozenset({src, tgt}))
    if alias_pairs and not groups:
        raise QualityError(
            "duplicates.json is empty but graph has also_known_as/translated_as"
        )
    covered = [frozenset(group.get("members") or []) for group in groups]
    for pair in alias_pairs:
        if not any(pair <= group for group in covered):
            raise QualityError(f"alias pair {set(pair)} missing from duplicates.json")

