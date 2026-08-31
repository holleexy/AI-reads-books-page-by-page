# 段1 FAIL 修正レポート

日付は 2026-08-30 である。
コミットしていない。push していない。xAI ライブ batch は回していない。

## Status

**DONE**

ブロッカー（`.ocr` 冊の suffix 誤認）と必須のデータ損失ギャップは直した。
未完了 batch の CLI `--offset` は挙動を変えず、再開は `next_offset` が勝つと文書化した。

## 何を変えたか

1. 出力先のファイル判定を `Path.suffix` から、`path.is_file()` または Hermes 作業記録の exact パスだけに変えた。存在しないパスはディレクトリとして作る。`採用入門.ocr` のような冊ディレクトリは成功する。
2. `extract_cache.json` が無いときは `batch_state.json` の `next_offset` を `covered_end` に使わない。先頭（または CLI `--offset`）から取り直す。
3. 空の `graph.json`（0 バイト、または entity 無し）は skip しない。`--force` 無しでやり直せる。
4. マニフェスト success 行の `item_count` をチャンク長にした。
5. 使い方に、未完了 batch は `next_offset` を優先すると書いた。

## テスト結果

リポ `.venv`:

```
Ran 71 tests in 0.143s
OK (skipped=3)
```

Semantica venv:

```
Ran 38 tests in 28.362s
OK
```

## `.ocr` batch が落ちないことの証明

検証者と同じ形のプローブ（モック抽出、本番 `run_batch`、`run_book_fn` 無し、Semantica venv）:

```
AI_Agent_x_BPR	success
採用入門.ocr	success
PROBE_OK
```

以前は `採用入門.ocr` が `output_dir must be a directory, not a file` で fail していた。

## 変更ファイル

- `book_semantica/paths.py`
- `book_semantica/pipeline.py`
- `book_semantica/batch.py`
- `book_semantica/discover.py`
- `book_semantica/cli.py`
- `docs/usage/13-semantica-books.md`
- `tests/test_book_semantica_batch.py`
- `tests/test_book_semantica_paths.py`
- `tests/test_book_semantica_pipeline.py`

`read_books.py` は未変更。FAISS / Neo4j は入れていない。
