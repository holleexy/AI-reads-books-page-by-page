# 段1 FAIL 修正 handoff

日付は 2026-08-30 である。
敵対的検証の Verdict は FAIL である。
レビューは `docs/plans/2026-08-30-batch-books-adversarial-review.md` である。
コミットしない。ライブ LLM は回さない。

## ブロッカー（必須）

`batch` が冊ディレクトリ `…/採用入門.ocr` を `RunConfig.output_dir` に渡す。
`pipeline._resolve_output_dir` と `batch._guard_output_dir` が `Path.suffix` をファイル判定に使う。
`.ocr` は拡張子に見えるが、ここはディレクトリ名である。
pending 50 のうち 4 冊がこの形である。
単冊 `run`（`output_dir=None`）は通る。

直し方: ファイル判定は `is_file()` と Hermes 作業記録の exact パスだけにする。
存在しないパスはディレクトリとして作る。Hermes の `.json` は従来どおり拒否する。
`book_key` が `.ocr` で終わる出力先は成功しなければならない。

テストは `run_book_fn` を差し替えずにこの判定を踏むこと。
fixture キーは `採用入門.ocr` または `ready.ocr` で、本番の `_resolve_output_dir` / `run_batch`→`run_book`（抽出はモック可）を通す。

## データ損失ギャップ（必須）

`extract_cache.json` が無く `complete=false` のとき、済みスライスを再抽出せず蓄積も空になる。
キャッシュが無いなら `covered_end` を 0 として取り直す。

空または `entities` が空の `graph.json` は skip しない（失敗した書き出しを `--force` 無しでやり直せる）。

## 任意（時間が足りれば）

未完了 batch が CLI `--offset` を捨てる件。`max(cli, next_offset)` にするか、文書で「再開は next_offset が勝つ」と明示する。
マニフェスト `item_count` をチャンク長にする。
Hermes sibling の拒否は範囲外（既存の exact 拒否のまま）。

## 禁止

前の handoff と同じ。`read_books.py` を触らない。FAISS / Neo4j を入れない。
