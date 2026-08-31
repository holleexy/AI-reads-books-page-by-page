# 欠落 extract_cache 再検証の生ログ

日付は 2026-08-30 である。
検証者はこの修正を書いていない。
ライブ xAI は呼んでいない。
リポ `.venv` に semantica は入れていない。

## 独立プローブ（本番 `run_batch`、`run_book_fn` 無し）

コマンド:

```bash
.venv/bin/python docs/plans/2026-08-30-batch-cache-offset-reverify-probe.py
```

要約:

```
PROBE4b_missing_cache	status=success	offset=0	seen=['命題A', '命題B']	is_ab=True	is_cd=False	error=None
PROBE4b_present_cache_AB	status=success	offset=2	seen=['命題C', '命題D']	is_ab=False	is_cd=True	error=None
PROBE4b_corrupt_json	status=success	offset=0	seen=['命題A', '命題B']	is_ab=True	is_cd=False	error=None
PROBE4b_json_array	status=success	offset=0	seen=['命題A', '命題B']	is_ab=True	is_cd=False	error=None
PROBE4b_empty_object	status=success	offset=2	seen=['命題C', '命題D']	is_ab=False	is_cd=True	error=None
PROBE4b_binary_not_utf8	status=fail	offset=0	seen=[]	is_ab=False	is_cd=False	error='utf-8' codec can't decode byte 0xff in position 0: invalid start byte
```

PROBE4b（欠落キャッシュ）の JSON:

```json
{
  "label": "PROBE4b_missing_cache",
  "cache_present_before": false,
  "status": "success",
  "offset": 0,
  "error": null,
  "seen": ["命題A", "命題B"],
  "cache_ids": ["命題A", "命題B"],
  "covered_end": 2,
  "is_ab": true,
  "is_cd": false
}
```

キャッシュあり再開:

```json
{
  "label": "PROBE4b_present_cache_AB",
  "seen": ["命題C", "命題D"],
  "offset": 2,
  "cache_ids": ["命題A", "命題B", "命題C", "命題D"],
  "covered_end": 4
}
```

壊れた JSON 文字列 `{not json`:

```json
{
  "label": "PROBE4b_corrupt_json",
  "seen": ["命題A", "命題B"],
  "offset": 0,
  "status": "success"
}
```

空オブジェクト `{}`:

```json
{
  "label": "PROBE4b_empty_object",
  "seen": ["命題C", "命題D"],
  "offset": 2,
  "cache_ids": ["命題C", "命題D"]
}
```

非 UTF-8 バイト:

```json
{
  "label": "PROBE4b_binary_not_utf8",
  "status": "fail",
  "offset": 0,
  "seen": [],
  "error": "'utf-8' codec can't decode byte 0xff in position 0: invalid start byte"
}
```

## unittest

```bash
.venv/bin/python -m unittest tests.test_book_semantica_batch tests.test_book_semantica_paths
```

```
Ran 44 tests in 0.126s
OK
```

## grep

```bash
rg '\.suffix' book_semantica --glob '*.py'
```

0 件。

```bash
rg '_effective_offset|_extract_cache_readable' book_semantica --glob '*.py'
```

`book_semantica/batch.py` のみ。86, 97, 109, 188 行。

`.ocr` テストは残っている:

- `tests.test_book_semantica_batch.OcrSuffixOutputDirTests.test_run_batch_ocr_book_key_calls_real_run_book`
- `tests.test_book_semantica_batch.OcrSuffixOutputDirTests.test_run_book_accepts_ocr_suffix_output_dir`
- `tests.test_book_semantica_paths.OutputPathTests.test_assert_output_directory_accepts_ocr_suffix_path`

## plan

```bash
.venv/bin/python -m book_semantica plan --repo-root /opt/AI-reads-books-page-by-page
```

フッタ:

```
skip	労務入門.ocr	2328	/opt/AI-reads-books-page-by-page/book_analysis/semantica/労務入門.ocr
pending=50 skip=1
```
