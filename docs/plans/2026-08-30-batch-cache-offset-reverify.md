# 欠落 extract_cache × run_batch 修正の敵対的再検証

検証日は 2026-08-30 である。
検証者はこの実装もキャッシュオフセット修正も書いていない。
前回の残ギャップは `docs/plans/2026-08-30-batch-books-adversarial-reverify.md` の PROBE4b である。
修正は DONE と主張されている（`docs/plans/2026-08-30-batch-cache-offset-fix.md`、同 `-fix-report.md`、同 `-evidence.md`）。
handoff と実装者レポートは証拠として使わず、独立プローブとコード読解で主張を崩した。
実装は直していない。
コミットもしていない。
リポ `.venv` へ `pip install semantica` していない。
xAI へのライブ batch は回していない。

## Verdict

**PASS_WITH_GAPS**

前回 PROBE4b が失っていた先頭スライスは、本番 `run_batch`（`run_book_fn` 無し）で取り直される。
欠落 `extract_cache.json`、`complete=false`、`next_offset=2`、limit=2 で、抽出に渡った text は `['命題A', '命題B']` である。
`命題C` / `命題D` だけではない。
この必須条件では FAIL にしない。

キャッシュが A/B を覆っているときは、第二チャンクは C/D だけである。
壊れた JSON 文字列と非 dict（配列）も、欠落と同じように offset 0 から A/B を取り直す。

残るギャップは二点である。
空の JSON object `{}` は「読める dict」と判定され、`next_offset=2` を信用する。
抽出は C/D だけになり、A/B は失われる。
非 UTF-8 バイトのキャッシュは `_effective_offset` が 0 に戻すが、`pipeline._read_json` が `UnicodeDecodeError` を呑まず、`run_batch` が `fail` になる。
抽出は走らない。

## Claim-by-claim

| claim | result | evidence |
| --- | --- | --- |
| 欠落 cache + 本番 `run_batch`: 抽出は A/B（PROBE4b） | PASS | 独立プローブ `PROBE4b_missing_cache`。`seen=['命題A', '命題B']`。`offset=0`。`cache_ids=['命題A', '命題B']`。前回の `['命題C', '命題D']` は再現しない |
| `_effective_offset` は cache 欠落時に `next_offset` を捨てる | PASS | `batch.py` 109-110 行。`_extract_cache_readable` がファイル欠落で False。CLI offset を返す |
| キャッシュありの未完了冊は `next_offset` で再開する | PASS | `PROBE4b_present_cache_AB`。`seen=['命題C', '命題D']`。`offset=2`。書き直し後の cache_ids は A〜D |
| 読めない / 壊れた cache は欠落と同じく 0 から取り直す | PASS_WITH_GAPS | 不正 JSON 文字列と JSON 配列は A/B。空 `{}` は C/D を取る。非 UTF-8 は status=fail、seen=[] |
| `_effective_offset` が cache ファイルを見る | PASS | `rg` は `batch.py` の `_extract_cache_readable` と 109 行の呼び出しだけ |
| 指定 unittest 44 OK | PASS | `.venv/bin/python -m unittest tests.test_book_semantica_batch tests.test_book_semantica_paths`。Ran 44、OK |
| `.ocr` テストが残り、`Path.suffix` ファイル判定は戻っていない | PASS | `test_run_batch_ocr_book_key_calls_real_run_book` あり。`rg '\.suffix' book_semantica --glob '*.py'` は 0 件 |
| 実リポ `plan` は pending=50 skip=1 | PASS | フッタ一致。労務入門は skip |

## 攻撃 1: PROBE4b 再実行

一時ディレクトリ。
知識 4 件（命題A〜D）。
`batch_state.json` は `complete=false`、`next_offset=2`。
`extract_cache.json` は置かない。
`run_book_fn` は渡さない。
モックは抽出、ontology、`build_graph`、`detect_conflicts`、`export_all` だけである。

抽出に渡った text:

```
['命題A', '命題B']
```

成功行の offset は 0 である。
書き直した cache の entity id も A/B である。
前回 PROBE4b の `first_two_extracted False` は消えた。
必須条件は成立する。

## 攻撃 2: キャッシュあり再開

同じ fixture に A/B を覆う `extract_cache.json`（`covered_end=2`）を置く。

```
seen ['命題C', '命題D']
offset 2
cache_ids ['命題A', '命題B', '命題C', '命題D']
covered_end 4
```

未完了冊は `next_offset` を使う。
済みスライスは再抽出しない。
主張どおりである。

## 攻撃 3: 読めない cache

不正 JSON 文字列 `{not json` では、抽出は A/B、offset は 0 である。
JSON 配列 `[1, 2]`（非 dict）も同じである。
`_extract_cache_readable` は `isinstance(payload, dict)` で False にする。

しかし空 object `{}` は dict なので True になる。
`_effective_offset` は `next_offset=2` を返す。
`accumulate_extract` は `cache_payload={}` を「キャッシュあり」と見なし、`covered_end=0` のまま `start = max(2, 0) = 2` になる。
抽出は C/D だけである。
cache_ids も C/D だけである。
A/B は失われる。
欠落ファイルと同じデータ損失が、空 object では残る。

非 UTF-8 バイト `\xff\xfe{not` では、`_effective_offset` 側は `UnicodeDecodeError` を捉えて offset=0 に戻す。
そのあと `pipeline._read_json` が同じファイルを読む。
こちらは `OSError` と `JSONDecodeError` しか捉えない。
`UnicodeDecodeError` が `run_batch` まで上がり、status は `fail` である。
seen は空である。
「欠落と同じく 0 から取り直す」は、このバイト列では成立しない。

## 攻撃 4: `_effective_offset` と cache ファイル

`book_semantica/batch.py` の判定は次である。

```86:112:book_semantica/batch.py
def _extract_cache_readable(output_dir: Path) -> bool:
    path = Path(output_dir) / EXTRACT_CACHE_FILENAME
    if not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return False
    return isinstance(payload, dict)


def _effective_offset(
    book: BookCandidate,
    *,
    offset: int,
    force: bool,
    output_dir: Path | None = None,
) -> int:
    if force:
        return int(offset or 0)
    state = book.batch_state or {}
    if state and not state.get("complete") and "next_offset" in state:
        cache_dir = Path(output_dir) if output_dir is not None else book.output_dir
        if not _extract_cache_readable(cache_dir):
            return int(offset or 0)
        return int(state["next_offset"])
    return int(offset or 0)
```

`run_batch` は 188-190 行で、その run が書く先 `out` を渡す。
cache ファイルを見ている。
見ている条件が「ファイルがあり、UTF-8 で JSON object である」だけである。
中身の `entities` も `covered_end` も見ない。
空 `{}` が通る理由はここである。

`pipeline._read_json` は例外集合が狭い。

```76:83:book_semantica/pipeline.py
def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None
```

`_effective_offset` が「読めない」とした非 UTF-8 を、蓄積側が再例外にする。
二関数の契約が揃っていない。

## 攻撃 5: unittest

```
Ran 44 tests in 0.126s
OK
```

実装者の 44 OK は再現する。
追加テスト `test_run_batch_missing_cache_reextracts_first_slice` は `run_book_fn` を渡さない。
`test_unreadable_cache_uses_cli_offset` は `{not json` だけを `_effective_offset` に渡す。
空 `{}` と非 UTF-8 の本番 `run_batch` はテストしていない。

## 攻撃 6: `.ocr` と suffix

`test_run_batch_ocr_book_key_calls_real_run_book` は残っている。
`test_run_book_accepts_ocr_suffix_output_dir` も残っている。
`test_assert_output_directory_accepts_ocr_suffix_path` も残っている。

```bash
rg '\.suffix' book_semantica --glob '*.py'
```

0 件である。
`Path.suffix` によるファイル判定は戻っていない。

## 攻撃 7: 実リポ plan

```
pending=50 skip=1
skip	労務入門.ocr	2328
```

前回どおりである。

## 実装者の Status DONE について

| 実装者の主張 | 再実行 |
| --- | --- |
| 欠落 cache で本番 `run_batch` が A/B を取る | 成立 |
| キャッシュありは `next_offset` で再開 | 成立 |
| 不正 JSON は CLI offset | 文字列の不正 JSON では成立。空 `{}` と非 UTF-8 では不成立 |
| unittest 44 OK | 成立 |
| `.ocr` / suffix 非回帰 | 成立 |

前回 PROBE4b の必須ギャップは閉じた。
DONE を削るほどではない。
空 object と非 UTF-8 は、同じ「読めない cache を 0 から取り直す」文面の穴である。

## 検証の範囲外

- 51 冊ライブ LLM
- 実装の修正
- リポ `.venv` への `pip install semantica`
- コミット

## 検証ステータス

DONE

レビュー: `docs/plans/2026-08-30-batch-cache-offset-reverify.md`
PROBE4b seen texts: `['命題A', '命題B']`
Verdict: PASS_WITH_GAPS
