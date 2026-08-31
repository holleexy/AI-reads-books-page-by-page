# 段1 残ギャップ: 欠落キャッシュ × run_batch

日付は 2026-08-30 である。
再検証 Verdict は PASS_WITH_GAPS である。
`.ocr` FAIL は消えた。残る必須ギャップは次である。

`run_batch` の `_effective_offset` が、`extract_cache.json` が無くても `batch_state.next_offset` を `RunConfig.offset` に入れる。
`accumulate_extract` はキャッシュ欠落時 `covered_end=0` にするが、`start = max(offset, covered_end)` で offset=2 が勝つ。
先頭スライスは再抽出されず失われる。

## 必須

キャッシュファイルが無い（または読めない）ときは `next_offset` を信用しない。
CLI `--offset`（既定 0）から取り直す。
テストは `run_book_fn` を差し替えず、本番 `run_batch` を踏むこと。
4 件の知識点、`complete=false`、`next_offset=2`、キャッシュ無し、limit=2 で、抽出に渡る text が先頭 2 件を含むことを断言する。

## 禁止

コミットしない。ライブ LLM しない。`read_books.py` を触らない。FAISS / Neo4j を入れない。`.ocr` 判定を suffix に戻さない。
