"""Build an OWL/SHACL ontology from a book summary via xAI."""

from __future__ import annotations

from typing import Any

from book_semantica.paths import DEFAULT_MODEL
from book_semantica.quality import normalize_datatype

JAPANESE_ONTOLOGY_INSTRUCTIONS = """クラスの name は IRI 用の ASCII CamelCase でよい。
label は必ず日本語で書け。
comment も日本語で書け。
プロパティの label も日本語。
文字列の range は xsd:string と一度だけ書け。xsd:xsd:string は禁止。
"""


def _slash_base(uri: str) -> str:
    if uri.endswith("#"):
        return uri
    if not uri.endswith("/"):
        return uri + "/"
    return uri


def normalize_ontology(ontology: dict, book_key: str = "book") -> dict[str, Any]:
    """Give every class and property a non-empty IRI (base + name)."""
    out = dict(ontology or {})
    base = out.get("uri") or out.get("base_uri") or f"https://books.local/{book_key}/"
    base = _slash_base(str(base))
    out["uri"] = base
    out.setdefault("name", f"{book_key}Ontology")

    classes = []
    for cls in out.get("classes") or []:
        item = dict(cls)
        name = item.get("name") or item.get("id") or item.get("label") or "Class"
        item["name"] = name
        uri = item.get("uri") or item.get("id") or ""
        if not str(uri).strip():
            item["uri"] = f"{base}{name}"
        classes.append(item)
    out["classes"] = classes

    properties = []
    for prop in out.get("properties") or []:
        item = dict(prop)
        name = item.get("name") or item.get("id") or item.get("label") or "property"
        item["name"] = name
        uri = item.get("uri") or item.get("id") or ""
        if not str(uri).strip():
            item["uri"] = f"{base}{name}"
        ranges = item.get("range")
        if isinstance(ranges, list):
            item["range"] = [
                normalize_datatype(str(r)) if r is not None else r for r in ranges
            ]
        elif ranges is not None:
            item["range"] = normalize_datatype(str(ranges))
        properties.append(item)
    out["properties"] = properties
    return out


def generate_ontology(summary: str, config) -> dict[str, Any]:
    from book_semantica.xai_provider import register_xai_provider

    register_xai_provider()
    from semantica.ontology import LLMOntologyGenerator

    model = getattr(config, "model", None) or DEFAULT_MODEL
    book_key = getattr(config, "book_key", "book")
    generator = LLMOntologyGenerator(provider="xai", model=model)
    raw = generator.generate_ontology_from_text(
        JAPANESE_ONTOLOGY_INSTRUCTIONS + "\nTEXT:\n" + summary,
        name=f"{book_key}Ontology",
        base_uri=f"https://books.local/{book_key}/",
    )
    return normalize_ontology(raw, book_key=book_key)
