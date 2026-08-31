# 段1 量産 FAIL 修正の敵対的再検証

検証日は 2026-08-30 である。
検証者はこの実装も FAIL 修正も書いていない。
前回 Verdict は FAIL（`docs/plans/2026-08-30-batch-books-adversarial-review.md`）。
修正は DONE と主張されている（`docs/plans/2026-08-30-batch-books-fail-fix.md`、`docs/plans/2026-08-30-batch-books-fail-fix-report.md`）。
handoff と実装者レポートは証拠として使わず、コマンド再実行と成果物、テスト、コード読解で主張を崩した。
実装は直していない。
コミットも push もしていない。
リポ `.venv` へ `pip install semantica` していない。
xAI へのライブ batch は回していない。
Hermes の作業記録へは書いていない。

## Verdict

**PASS_WITH_GAPS**

前回 FAIL の主因だった `.ocr` 冊の suffix 誤認は消えている。
一時ディレクトリ上で本番 `run_batch`（`run_book_fn` 無し、抽出と ontology だけモック、Semantica venv）を回すと、`AI_Agent_x_BPR` も `採用入門.ocr` も `success` であり、`output_dir must be a directory, not a file` は出ない。
`book_semantica/` に `Path.suffix` によるファイル判定は無い。
テストは `_resolve_output_dir` をモックせず、`run_book_fn` 無しの `run_batch` で `.ocr` を踏む。

必須だった空グラフ skip も直っている（0 バイトと `entities:[]` は `should_skip_book=False`）。
実リポの `plan` は `pending=50 skip=1`、労務入門は skip のままである。

残る必須ギャップはデータ損失である。
`extract_cache.json` 欠落かつ `complete=false` かつ `next_offset=2` を、本番の `run_batch` で踏むと、先頭 2 件は再抽出されない。
ユニットテストは `accumulate_extract(..., offset=0)` だけを見て、`batch._effective_offset` を踏んでいない。
実装者の Status DONE は、この経路では成立しない。

`.ocr` batch は落ちないので、今回の Verdict は FAIL ではない。

## 前回 FAIL は消えたか

消えた。

前回のブロッカーは `pipeline._resolve_output_dir` / `batch._guard_output_dir` が `Path.suffix` で冊ディレクトリ `採用入門.ocr` をファイルと誤認することだった。
いまの判定は `paths.assert_output_directory` であり、既存ファイルは `is_file()`、Hermes 作業記録は exact パスだけを拒否する。
suffix だけでは拒否しない。

## Claim-by-claim

| claim | result | evidence |
| --- | --- | --- |
| BLOCKER: `run_batch` + 実 `run_book` で `採用入門.ocr` が `output_dir must be a directory, not a file` を上げない | PASS | Semantica venv、TemporaryDirectory、抽出/ontology モック、`run_book_fn` 無し。`AI_Agent_x_BPR	success`、`採用入門.ocr	success`、error=None。graph.json は 1059 / 1065 bytes。前回と同じ失敗文は出ない。 |
| `_resolve_output_dir` / `_guard_output_dir` が `Path.suffix` で `.ocr` 冊 dir を拒否しない | PASS | `rg '\.suffix' book_semantica tests --glob '*.py'` は 0 件。`inspect.getsource` でも `_resolve_output_dir` / `_guard_output_dir` / `assert_output_directory` に `.suffix` は無い。`assert_output_directory` は `is_file()` と Hermes exact。存在しない `採用入門.ocr` はディレクトリとして通る。 |
| Hermes `semantica-knowledge-work.json` を output_dir にするとまだ raise する | PASS | `assert_output_directory(HERMES)` と `assert_safe_output_path(HERMES)` と `run_batch(..., output_dir=HERMES, dry_run=True)` はすべて `ForbiddenOutputPath: refusing to write Hermes graph: .../semantica-knowledge-work.json`。書き込みはしていない。 |
| テストが `_resolve_output_dir` をモックせずこの経路を踏む | PASS | `tests/test_book_semantica_batch.py` の `test_run_batch_ocr_book_key_calls_real_run_book` は `run_book_fn` を渡さない。`tests/test_book_semantica_pipeline.py` の `test_run_batch_ocr_key_succeeds_without_replacing_run_book` も同様。どちらも `_resolve_output_dir` を patch しない。抽出はモック、グラフ構築は Semantica 実体または `build_graph` patch。リポ `.venv` 71 OK、Semantica venv 52 OK。 |
| 欠落 `extract_cache.json` + complete=false: 先頭（または CLI offset）から再抽出する | PASS_WITH_GAPS | `accumulate_extract(offset=0)` では `命題A` `命題B` を取り直す（PROBE4a、ユニットテストと同じ）。本番 `run_batch` は `_effective_offset` が `next_offset=2` を `RunConfig.offset` に入れる。`start = max(offset, covered_end) = max(2, 0) = 2` になり、抽出は `命題C` `命題D` だけ。cache_ids もその 2 つ。A/B は失われる（PROBE4b）。テスト `test_missing_cache_reextracts_from_start_despite_next_offset` は `run_batch` を呼ばない。使い方 78 行の「`next_offset` があっても済みスライスを空のまま飛ばさない」は `batch` 経路では偽。 |
| 0 バイト `graph.json` と `entities:[]` は skip しない | PASS | PROBE5: `zero.ocr` has_graph=False skip=False。`emptyents.ocr` has_graph=False skip=False。実体あり `real.ocr` は skip=True。`discover.graph_has_entities` は size==0 / 不正 JSON / 空 entities を False にする。労務入門のライブ graph は 7945 bytes、entities 11、relationships 11 なので skip のまま。 |
| `plan` pending=50 skip=1、労務入門 skip | PASS | `.venv/bin/python -m book_semantica plan` は exit 0。フッタ `pending=50 skip=1`。`skip	労務入門.ocr	2328`。`batch_state.json` も `extract_cache.json` も無い。空グラフ規則はライブ労務入門を動かさない。 |
| dry-run / plan は LLM を呼ばない。dry-run はマニフェストを書かない | PASS | plan は `.venv` で 526ms、`import semantica` 無し。`batch --dry-run` は 433ms、stderr 空、実行前後とも `book_analysis/semantica/manifest.jsonl` は無い。`run_batch` は `dry_run` のとき `process_fn` を呼ばず continue。 |
| 既定 limit 80。全件は `--limit 0` または `--all-points` | PASS | `paths.DEFAULT_LIMIT` は 80。`parse_args(['run']).limit` は 80、`command` は `run`、`all_points` は False。`parse_args(['batch']).limit` は 80。`parse_args(['batch','--limit','0']).limit` は 0。`--all-points` は True。 |
| `read_books.py` 未変更 | PASS | `git rev-parse --is-inside-work-tree` は true。`git diff -- read_books.py` は空。`git status --porcelain -- read_books.py` は空。 |
| 品質ゲートはまだ `export_all` 上 | PASS | `export_all` は `sanitize_export_payload` のあと `_assert_written_quality` → `assert_artifact_quality`。本番 `run_book`（抽出モック）で `assert_artifact_quality` は 1 回呼ばれた。ギャップ: `test_run_batch_ocr_book_key_calls_real_run_book` は `export_all` を patch するのでゲートを踏まない。独立プローブと pipeline テストは踏む。 |
| FAISS / Neo4j 無し。リポ venv に semantica 無し | PASS | `rg 'faiss\|neo4j' book_semantica tests --glob '*.py'` は 0 件。`.venv/bin/python -c "import semantica"` は `ModuleNotFoundError` exit 1。`book_semantica/graph.py` の semantica import は関数内遅延。 |
| Hermes sibling は許可のままでよい（範囲外） | PASS | `assert_safe_output_path(/var/lib/happy/.local/state/hermes/book-graph-would-be-allowed.json)` は ALLOWED。親ディレクトリ `/var/lib/happy/.local/state/hermes` も ALLOWED。exact だけ拒否。書き込みはしていない。 |

## ブロッカー再攻撃

前回 FAIL プローブを同じ形で再実行した。
一時ディレクトリ。xAI は呼ばない。
Semantica venv。抽出と ontology だけモック。
`run_book_fn` は渡さないので `batch.py` が実 `pipeline.run_book` を import する。

```
AI_Agent_x_BPR	success	error=None
  graph=True size=1059
採用入門.ocr	success	error=None
  graph=True size=1065
```

`ForbiddenOutputPath` は出ない。
両方 success。
前回の失敗文は再現しない。

## データ損失（残ギャップ）

`accumulate_extract` はキャッシュ欠落時に `covered_end = 0` にする（`pipeline.py:126-127`）。
これは単体では正しい。
`run_batch` は先に `_effective_offset` を呼ぶ（`batch.py:85-91`）。
未完了なら CLI `--offset` を捨てて `next_offset` を `RunConfig.offset` に入れる。
そのあと `start = max(offset, covered_end)` なので、キャッシュが無くても `offset=2` が勝つ。

PROBE4a（`accumulate_extract` offset=0）:

```
seen ['命題A', '命題B']
PROBE4a OK
```

PROBE4b（本番 `run_batch`、`run_book_fn` 無し、CLI offset=0、limit=2）:

```
status success offset 2 error None
seen ['命題C', '命題D']
cache_ids ['命題C', '命題D']
covered_end 4
PROBE4b first_two_extracted False
```

使い方 `docs/usage/13-semantica-books.md` 78 行は「キャッシュが無いときは先頭（または CLI `--offset`）から取り直す」と書く。
76 行は「未完了 batch は `next_offset` を優先する」と書く。
両方を同時に満たす実装にはなっていない。
ユニットテストは 76 行側の合成を見ていない。

これは前回 FAIL の主因ではない。
必須修正としては未完了である。

## 空グラフ

`discover.graph_has_entities` はファイルが無い、0 バイト、不正 JSON、dict でない、`entities` が空リスト、のいずれでも False。
`should_skip_book` は `has_graph` が False なら skip しない。
実体が 1 件以上あり `batch_state` が無ければ skip（労務入門と同じパイロット扱い）。

ライブ労務入門は entities 11 なので skip のまま。
空グラフ規則はここを動かさない。

## テスト

リポ `.venv`（pipeline 無しの指定集合）:

```
Ran 71 tests in 0.092s
OK (skipped=3)
```

実装者の「71 OK skip 3」は再現する。

Semantica venv（xai / pipeline / quality / quality_gate / batch）:

```
Ran 52 tests in 20.342s
OK
```

実装者の「38 OK」は 4 モジュール集合の数字である。
こちらは batch を足して 52 であり、失敗は無い。

`.ocr` 経路を `run_book_fn` 無しで踏むテストはある。
欠落キャッシュを `run_batch` で踏むテストは無い。
空グラフの batch 再実行テストは `run_book_fn` を差し替える（skip 判定だけを見る）。

## 品質ギャップ（今回 FAIL にしない）

1. 欠落 `extract_cache.json` を本番 `run_batch` が踏むと、`_effective_offset` が済みスライスを飛ばし、蓄積は新スライスだけになる。
2. 未完了 batch は CLI `--offset` を捨てる（文書化した任意項目。キャッシュ欠落と合成すると必須ギャップになる）。
3. Hermes sibling と親ディレクトリは拒否されない（範囲外）。
4. `GraphBuilder(merge_entities=True)` はチャンク蓄積の実体数を畳む（前回どおり。今回のブロッカーではない）。
5. batch の一部テストはまだ `run_book_fn` モック、または `export_all` patch で品質ゲートを踏まない。

## 攻撃ごとの記録

### 1. FAIL プローブ再実行

TemporaryDirectory。2 冊。実 `run_batch`。抽出モック。
両方 success。`.ocr` は落ちない。

### 2. `.suffix` grep

`book_semantica/` と `tests/` の `.py` に `Path.suffix` による output_dir 判定は無い。
実行時ソース確認でも同じ。

### 3. ユニットテスト

上記 71 / 52。失敗無し。

### 4. 欠落キャッシュ

4 知識点。`next_offset=2`。`extract_cache.json` 無し。
`accumulate_extract` は A/B を取り直す。
`run_batch` は C/D だけ。

### 5. 空グラフ

0 バイトと `{"entities":[]}` は skip=False。
実体ありは skip=True。

### 6. 実リポ plan

```
.venv/bin/python -m book_semantica plan --repo-root /opt/AI-reads-books-page-by-page
```

exit 0。`pending=50 skip=1`。労務入門 skip。

### 7. Hermes

exact パスは raise。
sibling は ALLOWED（範囲外）。
書き込み無し。

### dry-run / 禁止事項

```
.venv/bin/python -m book_semantica batch --dry-run --repo-root /opt/AI-reads-books-page-by-page
```

exit 0。マニフェストは作られない。
`.venv` に semantica は無い。
`read_books.py` の git diff は空。
faiss / neo4j の import は `book_semantica/` に無い。

## 実装者の Status DONE について

| 実装者の主張 | 再実行 |
| --- | --- |
| `.ocr` batch が落ちない | 成立（独立プローブでも success） |
| suffix 判定をやめた | 成立 |
| 空グラフは skip しない | 成立 |
| 欠落キャッシュは先頭から取り直す | `accumulate_extract(offset=0)` では成立。本番 `run_batch` では不成立 |
| tests 71 OK skip 3 | 成立 |
| Semantica 38 OK | 集合を変えて 52 OK。失敗は無い |
| plan pending=50 skip=1 | 成立 |
| dry-run はマニフェストを書かない | 成立 |

DONE を削るのは `.ocr` ではない。
`batch` 経路のキャッシュ欠落である。
前回 FAIL を復活させるほどのブロッカーではない。

## 検証の範囲外

- 51 冊ライブ LLM
- Hermes グラフの作成
- 実装の修正
- リポ `.venv` への `pip install semantica`

## 実行したコマンド

```bash
.venv/bin/python -m book_semantica plan --repo-root /opt/AI-reads-books-page-by-page
.venv/bin/python -m book_semantica batch --dry-run --repo-root /opt/AI-reads-books-page-by-page
.venv/bin/python -c "import semantica"
git diff -- read_books.py
git status --porcelain -- read_books.py
rg -n 'faiss|neo4j' book_semantica/ tests/ --glob '*.py'
rg -n '\.suffix' book_semantica/ tests/ --glob '*.py'
.venv/bin/python -m unittest tests.test_book_semantica_batch tests.test_book_semantica_paths \
  tests.test_book_semantica_load tests.test_book_semantica_quality \
  tests.test_book_semantica_quality_gate tests.test_book_semantica_xai
PYTHONPATH=/opt/AI-reads-books-page-by-page \
  /var/lib/happy/.local/share/semantica/venv/bin/python -m unittest \
  tests.test_book_semantica_xai tests.test_book_semantica_pipeline \
  tests.test_book_semantica_quality tests.test_book_semantica_quality_gate \
  tests.test_book_semantica_batch
PYTHONPATH=/opt/AI-reads-books-page-by-page \
  /var/lib/happy/.local/share/semantica/venv/bin/python /tmp/batch_reverify_probes.py
```

加えて、一時ディレクトリ上の Python プローブ（モック抽出のみ。ライブ xAI 無し）で `.ocr` 2 冊 `run_batch`、suffix 判定、欠落キャッシュ（accumulate / run_batch）、空グラフ、Hermes exact / sibling、既定 80、品質ゲート 1 回呼び出しを確認した。

## 検証ステータス

DONE
