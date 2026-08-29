# Semantica が提供すること

[semantica-agi/semantica](https://github.com/semantica-agi/semantica) は、Python のナレッジグラフ基盤である。
自己紹介は「AI エージェント向けのオープンソース Palantir」である。
調査日時点で GitHub スターは約 11,000、ライセンスは MIT、導入は `pip install semantica` である。

宣伝の中心は規制業種の意思決定監査である。
本を読む用途そのものではない。
ただしパイプラインの中ほどは、非構造テキストからグラフとオントロジーを作る装置になっている。

## パイプライン

公式の流れは次である。

```
Sources → Ingest → Parse → Normalize → Split → Extract
  → Conflict Detection → Deduplication
  → Knowledge Graph
  → Ontology / Reasoning / Provenance / Decisions
  → Vector Store + Graph Store
  → Export / Visualize / REST / MCP / CLI
```

本リポジトリと重なる段階は、Ingest から Knowledge Graph と Ontology までである。
Decision Intelligence、Databricks、Snowflake、AML ルールは、本の学習用途では余分である。

## 本の情報からグラフを作る部品

Semantica は PDF を直接食べられる。
`FileIngestor` が PDF、DOCX、HTML、JSON、CSV などを読む。
スキャン画像 PDF は `DocumentParser(ocr=True)` で Tesseract を使える。

抽出は 2 系統ある。

**パターン／ルール系**は API キー不要で速い。
英語の固有名（Apple Inc.、Steve Jobs）向きである。
日本語の概念書（労務、人材マネジメント、ツボ）では、想起されるクラスが薄い。

**LLM 系**は精度が高い。
`NERExtractor(method="llm")` と `RelationExtractor(method="llm")` が、テキストからエンティティと関係を出す。
`LLMOntologyGenerator` はテキストを読んで、クラスとプロパティの JSON を直接返す。
日本語の概念体系をオントロジーにするなら、こちらが本命である。

グラフ化は `GraphBuilder` である。
エンティティ統合（`merge_entities=True`）、中心性、コミュニティ検出、最短経路、リンク予測がある。
オントロジー側は `OntologyGenerator` がデータからクラスを推定し、`OWLGenerator` と `SHACLGenerator` がスキーマを出す。
可視化はブラウザの Knowledge Explorer である。
書き出しは RDF Turtle、JSON-LD、OWL、Cypher、GraphML などである。

## 本リポジトリが持たないが Semantica が持つもの

| 能力 | 内容 |
| --- | --- |
| エンティティ抽出 | NER。LLM 経路なら日本語概念も取れる |
| 関係抽出 | subject / predicate / object |
| オントロジー | クラス推定、OWL、SHACL、SKOS、LLM 直接生成 |
| グラフ | 構築、分析、可視化、永続化（Neo4j など） |
| 重複と衝突 | 意味的デデュープ、矛盾フラグ |
| 出自 | W3C PROV-O。出典ファイルとページを付けられる |
| 検索 | グラフ走査とベクトル検索の併用 |
| 推論 | 前向き連鎖、Datalog、SPARQL |

## 本の学習用途での限界

Semantica は「本をページごとに勉強する」ツールではない。
目次スキップ、途中再開、冊単位の最終要約、Kindle 撮影、日本語 OCR  inbox は持たない。

事前テンプレートのドメインは healthcare、finance、legal、research、cybersecurity である。
労務、採用、BPR、法人営業の型は入っていない。
日本語向けの専用 NER モデルも、公式に前面には出ていない。

パターン抽出だけで 45 冊の日本語知識 JSON をグラフにすると、固有名は拾えても、著者の概念体系は崩れる。
LLM 抽出を使う前提で設計しないと、入れる意味が薄い。
