"""Write book-graph artifacts under book_analysis/semantica/{book_key}/."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from book_semantica.ontology import normalize_ontology
from book_semantica.paths import assert_safe_output_path
from book_semantica.quality import (
    assert_artifact_quality,
    collect_duplicates,
    drop_identity_edges,
    filter_conflicts,
    fix_shacl_datatypes,
    merge_duplicate_reports,
    render_owl,
)
from book_semantica.query import entity_id, entity_name, neighbors

ARTIFACT_NAMES = (
    "graph.json",
    "ontology.json",
    "ontology.owl",
    "shapes.ttl",
    "graph.html",
    "duplicates.json",
    "conflicts.json",
    "provenance.ttl",
)


def _write_text(path: Path, text: str) -> None:
    assert_safe_output_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: Any) -> None:
    _write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def owl_class_iris(text: str) -> list[str]:
    return [
        match
        for match in re.findall(r'<owl:Class[^>]*rdf:about="([^"]*)"', text)
        if match.strip()
    ]


def sanitize_export_payload(
    *,
    graph: dict,
    ontology: dict,
    duplicates: dict | None,
    conflicts: list | None,
    book_key: str,
) -> tuple[dict, dict, list]:
    """Re-apply the four quality fixes even if the caller skipped them."""
    graph["relationships"] = drop_identity_edges(graph.get("relationships") or [])
    ontology = normalize_ontology(ontology, book_key=book_key)
    graph_dups = collect_duplicates(
        graph.get("entities") or [],
        graph.get("relationships") or [],
    )
    duplicates = merge_duplicate_reports(duplicates, graph_dups)
    conflicts = filter_conflicts(conflicts)
    return ontology, duplicates, conflicts


def write_owl(ontology: dict, path: Path, book_key: str = "book") -> None:
    """Write OWL with Japanese rdfs:label. Do not use Semantica OWLExporter."""
    ontology = normalize_ontology(ontology, book_key=book_key)
    _write_text(path, render_owl(ontology))


def _shacl_from_generator(ontology: dict) -> str:
    from semantica.ontology import SHACLGenerator

    generator = SHACLGenerator(
        base_uri=ontology.get("uri") or "https://books.local/ns#",
    )
    graph = generator.generate(ontology)
    return generator.serialize(graph, format="turtle") or ""


def _fallback_shacl(ontology: dict) -> str:
    uri = ontology.get("uri") or "https://books.local/ns#"
    lines = [
        "@prefix sh: <http://www.w3.org/ns/shacl#> .",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        f"@prefix ex: <{uri}> .",
        "",
    ]
    for cls in ontology.get("classes") or []:
        name = cls.get("name") or "Class"
        label = cls.get("label") or name
        lines.append(f"ex:{name}Shape a sh:NodeShape ;")
        lines.append(f"  sh:targetClass ex:{name} ;")
        lines.append(f'  rdfs:label "{label}" .')
        lines.append("")
    return "\n".join(lines)


def render_shacl(ontology: dict, book_key: str = "book") -> str:
    """Always collapse xsd:xsd: after generate or fallback."""
    ontology = normalize_ontology(ontology, book_key=book_key)
    text = ""
    try:
        text = _shacl_from_generator(ontology)
    except Exception:
        text = ""
    if not str(text).strip():
        text = _fallback_shacl(ontology)
    text = fix_shacl_datatypes(text)
    if not text.endswith("\n"):
        text += "\n"
    return text


def write_shacl(ontology: dict, path: Path, book_key: str = "book") -> None:
    _write_text(path, render_shacl(ontology, book_key=book_key))


def _assert_written_quality(
    written: dict[str, Path],
    *,
    ontology: dict,
    duplicates: dict,
    conflicts: list,
    graph: dict,
) -> None:
    owl = written["ontology.owl"].read_text(encoding="utf-8")
    shacl = written["shapes.ttl"].read_text(encoding="utf-8")
    assert_artifact_quality(
        owl=owl,
        shacl=shacl,
        duplicates=duplicates,
        conflicts=conflicts,
        ontology=ontology,
        graph=graph,
    )


def repair_export(
    out_dir: Path,
    *,
    graph: dict,
    ontology: dict,
    book_key: str,
    conflicts: list | None = None,
    duplicates: dict | None = None,
) -> dict[str, Path]:
    """Rewrite OWL, SHACL, duplicates, conflicts from existing graph/ontology. No LLM."""
    existing = duplicates
    dups_path = out_dir / "duplicates.json"
    if existing is None and dups_path.is_file():
        existing = json.loads(dups_path.read_text(encoding="utf-8"))
    ontology, duplicates, cleaned = sanitize_export_payload(
        graph=graph,
        ontology=ontology,
        duplicates=existing,
        conflicts=conflicts,
        book_key=book_key,
    )
    written: dict[str, Path] = {}
    written["graph.json"] = out_dir / "graph.json"
    _write_json(written["graph.json"], graph)
    written["ontology.json"] = out_dir / "ontology.json"
    _write_json(written["ontology.json"], ontology)
    written["ontology.owl"] = out_dir / "ontology.owl"
    write_owl(ontology, written["ontology.owl"], book_key=book_key)
    written["shapes.ttl"] = out_dir / "shapes.ttl"
    write_shacl(ontology, written["shapes.ttl"], book_key=book_key)
    written["duplicates.json"] = out_dir / "duplicates.json"
    _write_json(written["duplicates.json"], duplicates)
    written["conflicts.json"] = out_dir / "conflicts.json"
    _write_json(written["conflicts.json"], cleaned)
    _assert_written_quality(
        written,
        ontology=ontology,
        duplicates=duplicates,
        conflicts=cleaned,
        graph=graph,
    )
    return written


def write_html(graph: dict, path: Path, title: str) -> None:
    assert_safe_output_path(path)
    wrote = False
    try:
        from semantica.visualization import KGVisualizer

        visualizer = KGVisualizer()
        visualizer.visualize_network(
            graph,
            output="html",
            file_path=path,
        )
        wrote = path.is_file() and path.stat().st_size > 0
    except Exception:
        wrote = False
    if not wrote:
        _write_text(path, render_fallback_html(graph, title))


def render_fallback_html(graph: dict, title: str) -> str:
    entities = graph.get("entities") or []
    payload = json.dumps(graph, ensure_ascii=False)
    rows = []
    for entity in entities:
        name = entity_name(entity)
        eid = entity_id(entity)
        etype = entity.get("type") or entity.get("entity_type") or ""
        book_key = entity.get("book_key") or (entity.get("metadata") or {}).get("book_key") or ""
        page = entity.get("page")
        if page is None:
            page = (entity.get("metadata") or {}).get("page")
        page_label = "" if page is None else str(page)
        neighbor_names = ", ".join(
            item["name"] for item in neighbors(graph, name)["neighbors"]
        )
        rows.append(
            "<tr>"
            f'<td><a href="#n-{eid}">{name}</a></td>'
            f"<td>{etype}</td>"
            f"<td>{book_key}</td>"
            f"<td>{page_label}</td>"
            f"<td>{neighbor_names}</td>"
            "</tr>"
        )
    table = "\n".join(rows)
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>
    body {{ font-family: sans-serif; margin: 1.5rem; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ccc; padding: 0.4rem 0.6rem; text-align: left; }}
    #detail {{ margin-bottom: 1.5rem; padding: 1rem; background: #f7f7f7; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <p>項目をクリックすると近傍の結びを表示する。Hermes explorer（8766）ではない。</p>
  <div id="detail">項目を選ぶ。</div>
  <table>
    <thead>
      <tr><th>項目</th><th>種類</th><th>冊</th><th>ページ</th><th>近傍</th></tr>
    </thead>
    <tbody>
      {table}
    </tbody>
  </table>
  <script>
    const graph = {payload};
    const detail = document.getElementById("detail");
    function neighborsOf(id) {{
      const rels = graph.relationships || [];
      const names = {{}};
      (graph.entities || []).forEach((e) => {{
        const eid = e.id || e.entity_id || e.name || e.text;
        names[eid] = e.name || e.text || eid;
      }});
      const found = [];
      rels.forEach((rel) => {{
        const src = rel.source || rel.subject;
        const tgt = rel.target || rel.object;
        if (src === id) found.push({{id: tgt, name: names[tgt] || tgt, rel: rel.type || rel.predicate}});
        if (tgt === id) found.push({{id: src, name: names[src] || src, rel: rel.type || rel.predicate}});
      }});
      return found;
    }}
    document.querySelectorAll("a[href^='#n-']").forEach((a) => {{
      a.addEventListener("click", (ev) => {{
        ev.preventDefault();
        const id = a.getAttribute("href").slice(3);
        const hops = neighborsOf(id);
        const list = hops.map((h) => h.name + " (" + h.rel + ")").join(" / ") || "結びなし";
        detail.textContent = a.textContent + " の近傍: " + list;
      }});
    }});
  </script>
</body>
</html>
"""


def render_book_provenance(book_key: str, entities: list[dict]) -> str:
    """PROV-O TTL that always records book_key and page when present."""
    lines = [
        "@prefix prov: <http://www.w3.org/ns/prov#> .",
        "@prefix foaf: <http://xmlns.com/foaf/0.1/> .",
        f"@prefix book: <https://books.local/{book_key}/> .",
        "",
        "book:source a prov:Entity ;",
        f'  foaf:name "{book_key}" ;',
        f'  book:book_key "{book_key}" .',
        "",
    ]
    for entity in entities:
        eid = entity_id(entity) or "entity"
        page = entity.get("page")
        if page is None:
            page = (entity.get("metadata") or {}).get("page")
        lines.append(f"book:{eid} a prov:Entity ;")
        lines.append(f'  book:book_key "{book_key}" ;')
        lines.append("  prov:wasDerivedFrom book:source")
        if page is not None:
            lines[-1] += " ;"
            lines.append(f'  book:page "{page}" ;')
            lines.append(f'  prov:atLocation "{page}" .')
        else:
            lines[-1] += " ."
        lines.append("")
    return "\n".join(lines)


def write_provenance(manager: Any | None, path: Path, book_key: str, entities: list[dict]) -> None:
    del manager
    _write_text(path, render_book_provenance(book_key, entities))


def export_all(
    out_dir: Path,
    *,
    graph: dict,
    ontology: dict,
    duplicates: dict,
    conflicts: list,
    book_key: str,
    provenance_manager: Any | None = None,
) -> dict[str, Path]:
    assert_safe_output_path(out_dir / "graph.json")
    out_dir.mkdir(parents=True, exist_ok=True)
    ontology, duplicates, conflicts = sanitize_export_payload(
        graph=graph,
        ontology=ontology,
        duplicates=duplicates,
        conflicts=conflicts,
        book_key=book_key,
    )
    written: dict[str, Path] = {}
    written["graph.json"] = out_dir / "graph.json"
    _write_json(written["graph.json"], graph)
    written["ontology.json"] = out_dir / "ontology.json"
    _write_json(written["ontology.json"], ontology)
    written["ontology.owl"] = out_dir / "ontology.owl"
    write_owl(ontology, written["ontology.owl"], book_key=book_key)
    written["shapes.ttl"] = out_dir / "shapes.ttl"
    write_shacl(ontology, written["shapes.ttl"], book_key=book_key)
    written["graph.html"] = out_dir / "graph.html"
    write_html(graph, written["graph.html"], title=f"{book_key} のグラフ")
    written["duplicates.json"] = out_dir / "duplicates.json"
    _write_json(written["duplicates.json"], duplicates)
    written["conflicts.json"] = out_dir / "conflicts.json"
    _write_json(written["conflicts.json"], conflicts)
    written["provenance.ttl"] = out_dir / "provenance.ttl"
    write_provenance(
        provenance_manager,
        written["provenance.ttl"],
        book_key,
        graph.get("entities") or [],
    )
    _assert_written_quality(
        written,
        ontology=ontology,
        duplicates=duplicates,
        conflicts=conflicts,
        graph=graph,
    )
    return written
