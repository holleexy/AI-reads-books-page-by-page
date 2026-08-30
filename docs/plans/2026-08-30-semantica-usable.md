# Semantica 本グラフを使える状態にする

> **For agentic workers:** 実装はサブエージェント。完了後に別サブエージェントが証拠付き敵対的検証をする。コミットはしない。

**Goal:** `docs/analysis/2026-08-29-semantica-fit/09-will-those-four-land.md` の 4 項目と「追加作業」を、このリポジトリから 1 冊で実行できる状態にする。

**Architecture:** Hermes の Semantica 0.6.5 venv を呼ぶ。本読みリポへ `pip install semantica` しない。本のグラフは `book_analysis/semantica/` にだけ書く。xAI は Semantica の `OpenAIProvider(base_url=...)` を `xai` として登録する。1 冊（『労務入門』）の要約でクラス、知識点の先頭 N 件でインスタンス。横断統合はしない。

**Tech Stack:** Semantica 0.6.5（`/var/lib/happy/.local/share/semantica/venv`）、xAI Grok、このリポの知識 JSON と最終要約。

---

## 固定制約

- Semantica ソースをこのリポへコピーしない。
- このリポの `.venv` へ `semantica` を入れない。
- `/var/lib/happy/.local/state/hermes/semantica-knowledge-work.json` へ書かない。出力パスがそのファイルなら例外で止める。
- Hermes explorer（ポート 8766）を本グラフの画面にしない。本用は別ディレクトリの HTML、必要なら別ポート 8767。
- 既存約 10 万件を取り直さない。出典は冊必須、ページはあれば付ける。
- パターン NER だけで日本語概念を取らない。NER と関係は `method="llm"`、provider は `xai`。
- 51 冊を一度に投げない。既定は 1 冊、知識点は `--limit`（既定 80）。
- `read_books.py` の抽出パイプラインは変えない（下流 1 段）。
- コミットしない。ブランチ `feat/semantica-books` 上で作業する。

## ファイル

| パス | 役割 |
| --- | --- |
| `book_semantica/paths.py` | SEMANTICA_PYTHON、出力根、Hermes 禁止パス |
| `book_semantica/xai_provider.py` | `xai` を provider_registry に登録。OpenAIProvider + `https://api.x.ai/v1` + `XAI_API_KEY` |
| `book_semantica/load_book.py` | 知識 JSON と最終要約の読込。文字列を `{text, page}` に正規化 |
| `book_semantica/provenance.py` | 各エンティティに `book_key`、あれば `page` |
| `book_semantica/ontology.py` | 要約 → `LLMOntologyGenerator` → OWL / SHACL |
| `book_semantica/extract.py` | 知識点 → LLM NER + RelationExtractor |
| `book_semantica/graph.py` | GraphBuilder、デデュープ、ConflictDetector |
| `book_semantica/export_artifacts.py` | JSON、OWL、SHACL、HTML、PROV |
| `book_semantica/query.py` | 項目名から近傍と経路 |
| `book_semantica/serve.py` | 静的 HTML を出す。explorer を 8767 で本ファイルだけ指す場合の起動 |
| `book_semantica/pipeline.py` | 1 冊の一連 |
| `book_semantica/cli.py` | CLI |
| `scripts/run_book_semantica.sh` | Semantica の Python で実行。BWS / XAI 注入。このリポの site-packages を PYTHONPATH に足さない |
| `tests/test_book_semantica_paths.py` | 禁止パス、出力先 |
| `tests/test_book_semantica_load.py` | 旧形式文字列、page 付き |
| `tests/test_book_semantica_xai.py` | 登録と base_url（Semantica venv が要るテストは skip 可） |
| `tests/test_book_semantica_pipeline.py` | LLM をモックして成果物ファイルが揃う |
| `docs/usage/13-semantica-books.md` | 使い方 |
| `book_analysis/semantica/README.md` | 出力の置き場 |

## 成功条件（09 の 4 項目 + 追加作業）

1. xAI を Semantica から呼べる（`provider="xai"`、`base_url=https://api.x.ai/v1`）。
2. 本用グラフが `book_analysis/semantica/{book_key}/` に残る。Hermes の knowledge-work.json は変わらない。
3. 1 冊から型付き項目と辺が出る（LLM。パターン NER ではない）。
4. クラス一覧が OWL と SHACL として残る。
5. グラフ HTML で項目と結びを辿れる（本用。8766 ではない）。
6. 項目名で近傍または経路を問い合わせできる。
7. 重複検出と矛盾検出の結果ファイルがある。
8. 出典に `book_key` がある。`page` は入力にあれば残る。
9. 『労務入門』（`労務入門.ocr`）で、キーがあれば `--limit` 付きの実走ができる。キーが無ければモック経路と使い方が揃っていればよい。

## API の足がかり（Semantica 0.6.5）

- Python: `/var/lib/happy/.local/share/semantica/venv/bin/python`
- `from semantica.semantic_extract.registry import provider_registry`
- `from semantica.semantic_extract.providers import OpenAIProvider, create_provider`
- `LLMOntologyGenerator(provider="xai", model="grok-4.6")`
- `NamedEntityRecognizer(method="llm", provider="xai", llm_model="grok-4.6")`
- `RelationExtractor(method="llm", provider="xai", llm_model="grok-4.6")`
- `GraphBuilder(merge_entities=True, resolve_conflicts=True)`
- `OWLExporter`、`semantica.ontology.SHACLGenerator`
- `DuplicateDetector` または GraphBuilder の merge
- `ConflictDetector`
- `ProvenanceManager`
- `KGVisualizer` で HTML
- Explorer は `GraphSession.from_file(path)`。使うならポート 8767。既定の画面は HTML で足りる。

入力例:

- 要約: `book_analysis/summaries/労務入門.ocr_final_001.md`
- 知識: `book_analysis/knowledge_bases/労務入門.ocr_knowledge.json`（2328 件、すべて文字列）
- book_key: `労務入門.ocr`

xAI 認証は `XAI_API_KEY` を Semantica 側の `api_key` に渡す。OAuth まで移植しなくてよい。起動スクリプトは既存 `run.sh` と同様に BWS でキーを注入してよい。
