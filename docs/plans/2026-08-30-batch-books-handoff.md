# 段1 量産（ファイル）handoff

日付は 2026-08-30 である。
オーケストレーターがサブエージェントへ委譲する。
実装はコミットしない。push しない。
51 冊のライブ LLM は回さない。

## ゴール

要約がある冊を列挙し、既存グラフがある冊を飛ばし、1 冊内は知識点の offset で再開できるバッチを、このリポジトリから実行できる状態にする。
正本はこれまでどおり `book_analysis/semantica/{book_key}/` である。
FAISS と Neo4j は入れない。

## 成功条件

1. `plan`（または同等）が、知識 JSON と最終要約がある冊を列挙する。`graph.json` がある冊は `skip` と分かる。『労務入門.ocr』は skip になる。
2. `batch` が、未作成の冊だけ `run_book` 相当を呼ぶ。既存グラフは `--force` 無しでは再実行しない。
3. 1 冊内の再開: `--offset` と `--limit`（チャンク）で知識点スライスだけ LLM 抽出する。済みスライスは再抽出せず、蓄積した entities/relations からグラフを組み直す。状態は冊ディレクトリの `batch_state.json`（名前は実装で固定して文書化する）。
4. マニフェストが残る。冊キー、件数、offset、成否、時刻、出力ディレクトリ。Hermes 作業記録のパスではない。置き場は `book_analysis/semantica/manifest.jsonl` がよい。
5. `--dry-run` / `plan` は LLM を呼ばない。
6. `read_books.py` は変更しない。完了後フックは「本体を触らない」制約のため、今は入れない。使い方に「要約後に batch を別途回す」と書く。
7. 品質ゲート（`export_all` の sanitize と assert）は既存のまま通る。
8. テストはモックで、列挙・skip・offset 再開・マニフェスト・Hermes 非書き込みを証明する。ライブ xAI は不要。
9. 使い方 `docs/usage/13-semantica-books.md` を更新する。

## 既定の件数

単冊 `run` の既定 `--limit 80` は変えない（試し読み互換）。
`batch` のチャンク既定も 80 でよい。
全件は `--limit 0` または `--all-points` のような明示が要る（全件が黙って走らないこと）。
テストは小さい fixture で足りる。

## 禁止

- このリポ `.venv` へ `pip install semantica`
- Hermes `semantica-knowledge-work.json` へ書く
- 既存知識 JSON の取り直し
- FAISS / Neo4j
- 51 冊ライブ LLM
- `read_books.py` の変更
- コミット / push
- Semantica ソースのベンダー化

## 既存の足がかり

- `book_semantica/pipeline.py` の `run_book` / `RunConfig`
- `book_semantica/load_book.py` の `load_knowledge` / `load_summary`
- `book_semantica/cli.py` の `run|query|serve|repair`
- `scripts/run_book_semantica.sh`（ Semantica venv。このリポ `.venv` を PYTHONPATH に足さない）
- 品質ゲート: `export_artifacts.sanitize_export_payload` と `assert_artifact_quality`

## 実装後に残すもの

- 変更ファイル一覧
- テストコマンドと結果
- 実リポで `plan`/`dry-run` を 51 冊に対して走らせた出力（LLM 無し）
- Status: DONE | DONE_WITH_CONCERNS | BLOCKED
