# Semantica usable 実装の引き渡し（敵対的レビュー後）

作業ブランチは `feat/semantica-books` である。
コミットしていない。
push していない。
Hermes グラフには書いていない。
このリポジトリの `.venv` へ `semantica` を入れていない。

**状態: DONE_WITH_CONCERNS**

敵対的レビュー（`docs/plans/2026-08-30-semantica-usable-adversarial-review.md`、Verdict: PASS_WITH_GAPS）の必須 8 件は直した。
ライブ `--limit 3` も走った。
捏造した成果物は無い。

## レビュー指摘への対応

| # | 指摘 | 対応 |
| --- | --- | --- |
| 1 | OWL の `owl:Class rdf:about` が空 | `ontology.normalize_ontology()` が `uri = base_uri + name` を埋める。`write_owl` は空 IRI なら自前フォールバック。テストは空 `rdf:about` を失敗にし、非空 Class を1件以上要求する |
| 2 | `provenance.ttl` に `book_key` / `page` が無い | Semantica `export_prov` は使わない。常に `export_artifacts.render_book_provenance()`。`book:book_key` は必須。`page` があれば `book:page`。テストは TTL に `book_key` を含むことを見る |
| 3 | GraphBuilder マージ後に `page` が落ちる | `graph.restore_entity_provenance()` がマージ前の実体から id/name で `book_key` と `page` を戻す |
| 4 | LLM 失敗が英語パターン NER へ落ちる | `NamedEntityRecognizer` を経由せず `get_entity_method("llm")` / `get_relation_method("llm")` を直接呼ぶ。失敗は `LLMExtractionError`。`ner_method: llm` は LLM 経路が走ったときだけ。空 NER では関係抽出を呼ばない |
| 5 | `conflicts.json` が空のまま通る | `detect_conflicts(..., method="value", property_name="definition")`。同一 id で definition が食い違う入力は非空になる。専用テストあり |
| 6 | 文書が query を成果物無しで使えるように読める | `docs/usage/13-semantica-books.md`。既定サブコマンドは `run`（ライブ LLM）。`--dry-run` は無い。`query` / `serve` は `book_analysis/semantica/{book_key}/graph.json` が必要 |
| 7 | 認証が `XAI_API_KEY` だけ | `scripts/run_book_semantica.sh` はリポ `.venv` の子プロセスで `book_semantica.resolve_xai_key`（`XAI_API_KEY` または Hermes xAI OAuth）を呼び、取れた値だけを Semantica 子へ `export XAI_API_KEY`。トークンは表示しない。`.venv` site-packages は Semantica の PYTHONPATH に足さない |
| 8 | モック OWL の IRI が空 | テスト用オントロジー dict に `uri` と日本語 `name` / `label`（労務、人材マネジメント）を付けた |

追加したモジュールは `book_semantica/resolve_xai_key.py` である。

## 作ったファイル

| パス | 役割 |
| --- | --- |
| `book_semantica/paths.py` | Semantica の Python、出力根、Hermes 禁止パス、画面ポート |
| `book_semantica/xai_provider.py` | `xai` を `provider_registry` に登録 |
| `book_semantica/resolve_xai_key.py` | 起動スクリプト用。キーを stdout に1行出す（ログには出さない） |
| `book_semantica/load_book.py` | 知識 JSON と最終要約の読込 |
| `book_semantica/provenance.py` | `book_key` と、あれば `page` |
| `book_semantica/ontology.py` | 要約から LLM オントロジー。クラス `uri` を埋める |
| `book_semantica/extract.py` | LLM NER / 関係。失敗は例外。パターンへ落とさない |
| `book_semantica/graph.py` | GraphBuilder、重複、矛盾、マージ後の出典復元 |
| `book_semantica/export_artifacts.py` | JSON、OWL、SHACL、HTML、自前 PROV |
| `book_semantica/query.py` | 項目名の近傍と経路 |
| `book_semantica/serve.py` | 静的 HTML。既定ポート 8767 |
| `book_semantica/pipeline.py` | 1冊の一連 |
| `book_semantica/cli.py` | CLI。既定は `run` |
| `book_semantica/__init__.py` | パッケージ |
| `book_semantica/__main__.py` | `python -m book_semantica` |
| `scripts/run_book_semantica.sh` | Semantica Python + キー解決。`.venv` を PYTHONPATH に混ぜない |
| `tests/test_book_semantica_paths.py` | 禁止パス、出力先、起動スクリプト |
| `tests/test_book_semantica_load.py` | 旧形式文字列、page、問い合わせ |
| `tests/test_book_semantica_xai.py` | 登録と base_url（Semantica が無いと skip） |
| `tests/test_book_semantica_pipeline.py` | モック成果物、空 IRI 拒否、矛盾、LLM 失敗、空 NER |
| `docs/usage/13-semantica-books.md` | 使い方 |
| `book_analysis/semantica/README.md` | 出力の置き場 |

`docs/usage/README.md` から 13 へリンクを足した。
`read_books.py` は変えていない。

## テストのコマンドと結果

リポジトリの `.venv`（Python 3.10）。Semantica を import するテストは skip する。

```bash
.venv/bin/python -m unittest \
  tests.test_book_semantica_paths \
  tests.test_book_semantica_load \
  tests.test_book_semantica_xai
```

結果（レビュー修正後）: `Ran 26 tests in 0.007s` / `OK (skipped=3)`。

Semantica の venv（Python 3.11）。`PYTHONPATH` はリポジトリ根だけ。`.venv` の site-packages は混ぜない。

```bash
PYTHONPATH=/opt/AI-reads-books-page-by-page \
  /var/lib/happy/.local/share/semantica/venv/bin/python -m unittest \
  tests.test_book_semantica_xai tests.test_book_semantica_pipeline
```

結果（レビュー修正後）: `Ran 8 tests in 18.675s` / `OK`。

内訳は次である。

- xAI 登録 3件。`base_url=https://api.x.ai/v1`、`model=grok-4.6`。キー無しは OPENAI に落とさない
- モックパイプライン。OWL は非空 `rdf:about`。`provenance.ttl` に `book_key`。マージ後の「労務」に `page=3`。`conflicts.json` は非空。`ner_method` はモック2タプルでは metadata に書かない
- `test_value_conflicts_are_detected`。同一 id で definition が食い違うと `detect_conflicts` が非空
- `test_llm_failure_does_not_use_english_pattern_ner`。上げる LLM は `LLMExtractionError`。英語文から PERSON/ORG は出ない
- `test_empty_llm_ner_skips_relations_without_pattern_fallback`。NER が空リストなら関係抽出を呼ばない

禁止パスのテストは、出力が Hermes の `semantica-knowledge-work.json` なら `ForbiddenOutputPath` で止まる。

## 実走したか

した。

`XAI_API_KEY` はシェルに無かった。
`scripts/run_book_semantica.sh` が Hermes xAI OAuth でトークンを解決し、Semantica 子へ渡した。
トークンの値は出していない。
長さは 786 だった。

コマンド（指定どおり `--limit 3` のまま）:

```bash
./scripts/run_book_semantica.sh --book-key 労務入門.ocr --limit 3
```

1回目は、ある知識点の NER が空リストになり、関係抽出が `No entities provided for relation extraction` で落ちた。
空 NER では関係抽出を呼ばないようにしてから、同じコマンドを再実行した。
2回目は成功した。
出力は `book_analysis/semantica/労務入門.ocr/` である。捏造ではない。

| ファイル | 確認 |
| --- | --- |
| `ontology.owl` | クラス 28。空 IRI 0。例: `https://books.local/労務入門.ocr/LaborAffairs` |
| `ontology.json` | 日本語ラベルあり（労務、人材マネジメント、メンバーシップ型雇用 など）。クラス name は英語 |
| `graph.json` | エンティティ 11、辺 11。日本語項目あり（労務、勤怠管理、給与計算、モグラ叩き）。英語名も混在（Labor、attendance management）。`book_key` は全て `労務入門.ocr`。先頭 3 件は旧形式文字列なので `page` は全て無し。`ner_method: llm` |
| `provenance.ttl` | `book:book_key "労務入門.ocr"` あり。`page` は入力に無いので無し |
| `conflicts.json` | 長さ 1（関係の confidence 衝突）。空ではない |
| `shapes.ttl` | SHACL あり |
| `graph.html` | 約 4.8MB。Plotly |

問い合わせは成果物がある状態で動く。

```bash
./scripts/run_book_semantica.sh query --book-key 労務入門.ocr --name 労務
```

## Hermes グラフを書いていないことの根拠

コードが書く先は `book_analysis/semantica/{book_key}/` だけである。
出力パスが `/var/lib/happy/.local/state/hermes/semantica-knowledge-work.json` なら例外にする。
モックパイプラインは一時ディレクトリへ書き、その前後で Hermes ファイルの mtime が変わらないことを断言している。

ライブ前後の Hermes グラフ SHA-256 はどちらも次である。

`2f7621ba93571979be49f4307b483aef178d2575d48ec77c5daa9345a9b88cc2`

ノード数は 167。
JSON に「労務入門」は含まれない。

## 残る隙間

1. ライブ OWL のクラス name と `rdfs:label` は英語（LaborAffairs など）である。日本語は `ontology.json` の `label` とグラフ項目名にある。レビューは「日本語クラス名または日本語エンティティラベル」なので後者は満たす。
2. ライブ NER は同一概念の日英ペアを出すことがある（労務 と Labor）。
3. 労務入門の先頭知識点は旧形式の文字列なので、`--limit 3` では `page` は付かない。出典は冊までである。既存約 10 万件は取り直していない。
4. GraphBuilder / ConflictDetector の進捗ログが非常に多い。結果ファイルは出る。
5. `--explorer` は `semantica.explorer` を 8767 で本ファイルに向ける。入力形式は ContextGraph 前提なので、既定の画面は `graph.html` である。未検証のままである。
6. 知識点ごとの LLM 呼び出しは件数がそのまま費用になる。既定 80 の前に `--limit` を小さくした方がよい。

## 起動時の約束

`scripts/run_book_semantica.sh` は `SEMANTICA_PYTHON` を使う。
このリポジトリの `.venv` site-packages を Semantica の `PYTHONPATH` から外す。
リポジトリ根を `PYTHONPATH` に足す。
キー解決は `XAI_API_KEY`、次に Hermes xAI OAuth（リポ `.venv` の子プロセス）、次に `bws run` である。
トークンは表示しない。
