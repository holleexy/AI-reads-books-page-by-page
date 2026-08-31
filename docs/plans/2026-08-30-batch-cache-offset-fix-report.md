# 欠落 extract_cache × run_batch 修正レポート

日付は 2026-08-30 である。
コミットしていない。push していない。xAI ライブ batch は回していない。
`read_books.py` は未変更である。
`.ocr` のディレクトリ判定は suffix に戻していない。

## Status

**DONE**

`extract_cache.json` が無い（または読めない）とき、`run_batch` は `batch_state.next_offset` を捨てて CLI `--offset`（既定 0）から取り直す。
キャッシュがある未完了冊は、従来どおり `next_offset` が CLI offset に勝つ。

## 何を変えたか

`book_semantica/batch.py` の `_effective_offset` が、未完了かつ `next_offset` があるだけで再開位置を決めていた。
`accumulate_extract` はキャッシュ欠落時に `covered_end=0` にするが、`start = max(offset, covered_end)` なので、offset=2 が入ると先頭スライスは再抽出されない。

いまは出力先の `extract_cache.json` がファイルとして読め、かつ JSON object であるときだけ `next_offset` を使う。
欠落・不正 JSON・非 dict は CLI offset に戻す。
判定に使うディレクトリは、その run が書く先（`run_batch` が渡す `out`）である。

## 変更ファイル

- `book_semantica/batch.py`
- `tests/test_book_semantica_batch.py`
- `docs/plans/2026-08-30-batch-cache-offset-fix-report.md`（本ファイル）
- `docs/plans/2026-08-30-batch-cache-offset-fix-evidence.md`

`read_books.py` は未変更。
`book_semantica/paths.py` の `.ocr` 判定は未変更。
FAISS / Neo4j は入れていない。

## テスト結果

リポ `.venv`:

```
.venv/bin/python -m unittest tests.test_book_semantica_batch tests.test_book_semantica_paths
Ran 44 tests in 0.158s
OK
```

`.ocr` 回帰（同スイート内）:

- `test_run_batch_ocr_book_key_calls_real_run_book` ok
- `test_run_book_accepts_ocr_suffix_output_dir` ok
- `test_assert_output_directory_accepts_ocr_suffix_path` ok
- `book_semantica/` に `Path.suffix` によるファイル判定は無い

詳細は `docs/plans/2026-08-30-batch-cache-offset-fix-evidence.md` である。

## 本番 run_batch が A/B を取り直すことの証明

PROBE4b と同じ条件を、`run_book_fn` 無しの本番 `run_batch` で踏む。

fixture:

- 知識 4 件（命題A〜D）
- `batch_state.json`: `complete=false`, `next_offset=2`
- `extract_cache.json` 無し
- `limit=2`, CLI `offset=0`

テスト `test_run_batch_missing_cache_reextracts_first_slice` は `run_book_fn` を渡さない。
`batch.run_batch` が実 `pipeline.run_book` を import する。
モックは抽出・ontology と、リポ `.venv` 用の `build_graph` / `detect_conflicts` / `export_all` だけである。

断言:

- 抽出に渡った text は `["命題A", "命題B"]` である（`命題C`/`命題D` だけではない）
- 成功行の `offset` は `0` である（`next_offset=2` を捨てた）
- 書き直した `extract_cache.json` の entity id も A/B である

キャッシュがある場合の単体テスト `test_present_cache_uses_next_offset` は、同じ未完了 state で `_effective_offset(..., offset=0)` が `2` を返す。
