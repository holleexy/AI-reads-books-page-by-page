# 欠落 extract_cache 修正の検証記録

日付は 2026-08-30 である。
ライブ xAI は呼んでいない。
リポ `.venv` に semantica は入れていない。

## 指定コマンド

```bash
.venv/bin/python -m unittest tests.test_book_semantica_batch tests.test_book_semantica_paths
```

```
Ran 44 tests in 0.158s
OK
```

## 追加したテスト

| テスト | 何を踏むか |
| --- | --- |
| `test_run_batch_missing_cache_reextracts_first_slice` | 本番 `run_batch`（`run_book_fn` 無し）。欠落キャッシュ + `next_offset=2` + limit=2。抽出 text が A/B |
| `test_missing_cache_uses_cli_offset` | `_effective_offset`: キャッシュ無し → 0 / CLI offset |
| `test_unreadable_cache_uses_cli_offset` | `_effective_offset`: 壊れた JSON → CLI offset |
| `test_present_cache_uses_next_offset` | `_effective_offset`: キャッシュあり → `next_offset=2` |
| `test_missing_cache_reextracts_from_start_despite_next_offset` | 既存。`accumulate_extract(offset=0)` 経路。残している |

## 本番経路のモック範囲

`test_run_batch_missing_cache_reextracts_first_slice` が差し替えるもの:

- `extract_entities_relations`（抽出 text を記録する）
- `generate_ontology`
- `book_semantica.graph.build_graph`
- `book_semantica.graph.detect_conflicts`
- `book_semantica.pipeline.export_all`

渡さないもの:

- `run_book_fn`（本番 `pipeline.run_book` が走る）

## `.ocr` 非回帰

```bash
.venv/bin/python -m unittest \
  tests.test_book_semantica_batch.MissingCacheResumeTests \
  tests.test_book_semantica_batch.EffectiveOffsetTests \
  tests.test_book_semantica_batch.OcrSuffixOutputDirTests \
  tests.test_book_semantica_paths.OutputPathTests.test_assert_output_directory_accepts_ocr_suffix_path \
  -v
```

```
test_missing_cache_reextracts_from_start_despite_next_offset ... ok
test_run_batch_missing_cache_reextracts_first_slice ... ok
test_missing_cache_uses_cli_offset ... ok
test_present_cache_uses_next_offset ... ok
test_unreadable_cache_uses_cli_offset ... ok
test_resolve_output_dir_accepts_ocr_directory_name ... ok
test_resolve_output_dir_rejects_existing_file ... ok
test_resolve_output_dir_rejects_hermes_work_json ... ok
test_run_batch_ocr_book_key_calls_real_run_book ... ok
test_run_book_accepts_ocr_suffix_output_dir ... ok
test_assert_output_directory_accepts_ocr_suffix_path ... ok
Ran 11 tests in 0.059s
OK
```

`rg '\.suffix' book_semantica --glob '*.py'` は 0 件である。
