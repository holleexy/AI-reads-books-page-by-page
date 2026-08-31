# 段1 量産（ファイル）敵対的検証

検証日は 2026-08-30 である。
検証者はこの実装を書いていない。
handoff 文書は証拠として使わず、コマンド再実行と成果物、テスト、コード読解で主張を崩した。
実装は直していない。
コミットも push もしていない。
リポ `.venv` へ `pip install semantica` していない。
xAI へのライブ batch は回していない。
Hermes の作業記録へは書いていない。

## Verdict

**FAIL**

`plan` と `--dry-run` と既定 `--limit 80` と skip 列挙は、実装者の数字どおり動く。
しかし本番の `batch` は冊出力先を `RunConfig.output_dir` に必ず渡し、`Path.suffix` があるパスをファイルと誤認して落とす。
使い方が例にしている `./scripts/run_book_semantica.sh batch --book-key 採用入門.ocr` は、モック無しの `run_book` 経路で `ForbiddenOutputPath: output_dir must be a directory, not a file` になる。
pending 50 冊のうち 4 冊がこの形である。
テストは `ready.ocr` を使うが `run_book_fn` を差し替えてこの判定を踏まない。
Status DONE は成立しない。

## Claim-by-claim

| claim | result | evidence |
| --- | --- | --- |
| 1. `plan` は知識 JSON と最終要約がある冊を列挙する。`graph.json` がある冊は skip。労務入門.ocr は skip | PASS_WITH_GAPS | `.venv/bin/python -m book_semantica plan` は exit 0。フッタは `pending=50 skip=1`。`skip	労務入門.ocr	2328`。知識 JSON 51、最終要約キー 51、plan 51。知識だけで要約が無い冊は 0、要約だけで知識が無い冊は 0、pending かつ `has_graph` は 0。保存済み `docs/plans/2026-08-30-batch-books-plan-output.txt` との差分は先頭 4 行のコメントだけ。本体は一致。ギャップ: skip は `graph.json` の `is_file()` だけを見る（`discover.py:90`、`should_skip_book` は `discover.py:53-66`）。0 バイトの `graph.json` も実体空の `{"entities":[]}` も skip になる。 |
| 2. `batch` は未作成の冊だけ処理する。既存グラフは `--force` 無しでは再実行しない | FAIL | 層としては正しい。`should_skip_book` はグラフがあり `batch_state` が無いか `complete` が真なら skip。`--force` で False。モック経路では skip 冊の `run_book_fn` は呼ばれず、`--force` では `done.ocr` と `ready.ocr` の両方が呼ばれた。しかし本番経路（`run_book_fn` 無し）は `batch.py:192-199` で `output_dir=out` を必ず渡す。`pipeline.py:53-61` は `candidate.suffix` があれば例外にする。`採用入門.ocr` の出力先は suffix が `.ocr` なので、モック無し `run_batch` は `status=fail`、`error=output_dir must be a directory, not a file`。同じ fixture で `AI_Agent_x_BPR`（suffix 無し）は `success`。単冊 `run`（`output_dir=None`）は `.ocr` でも成功する。pending で suffix がある冊は 4: `BtoBグロースプレイブック.ocr`、`バックオフィス業務のすべてがわかる本.ocr`、`採用入門.ocr`、`社内SE1年目から貢献！-情シス-企画・開発・運用-107のルール_00.ocr`。 |
| 3. 1冊内再開。`--offset`+`--limit` はそのスライスだけ LLM 抽出。済みは再抽出せず、蓄積からグラフを組み直す。状態は `batch_state.json` | PASS_WITH_GAPS | `accumulate_extract` は `start = max(offset, covered_end)`（`pipeline.py:146-160`）。キャッシュがあるとき 2+2 で実体 4、2 回目の抽出は `命題C` `命題D` だけ。`batch_state.json` と `extract_cache.json` を書く。実装者の「キャッシュは `extract_cache.json` と `batch_state.json`」はコードどおり。ギャップ 1: `extract_cache.json` が無く `complete=false` のとき、済みスライスは再抽出しないが蓄積実体は空になり、グラフは新スライスだけになる。ギャップ 2: `batch._effective_offset`（`batch.py:86-92`）は未完了なら CLI の `--offset` を捨てて `next_offset` を使う。`--force` 無しでは先へ飛ばせない。ギャップ 3: 単冊 `run_book` の 2 チャンクでは Semantica `GraphBuilder(merge_entities=True)` が実体を畳む（抽出 4 件でも `graph.json` の entities は 1）。再開キャッシュの union は成立するが、グラフが蓄積の写しではない。 |
| 4. マニフェストは `book_analysis/semantica/manifest.jsonl`。冊キー、件数、offset、成否、時刻、出力ディレクトリ。Hermes パスではない | PASS_WITH_GAPS | `MANIFEST_RELPATH` は `book_analysis/semantica/manifest.jsonl`（`paths.py:24`）。`append_manifest` は repo_root 配下。実リポで `--dry-run` 後も `manifest.jsonl` は無い。モック本番相当では skip と success が 1 行ずつ付き、`output_dir` は Hermes ファイルと不一致、パスに `hermes` を含まない。行のキーは `book_key` `status` `offset` `limit` `item_count` `total_items` `output_dir` `timestamp`（失敗時は `error`）。ギャップ: success 行の `item_count` はスライス長ではなく `total_items` と同じ。Hermes ディレクトリを `--output-dir` にすると exact ファイル以外は拒否されない（後述）。 |
| 5. `--dry-run` / `plan` は LLM を呼ばない | PASS | `plan` は `.venv` で 429ms、stderr 空、`import semantica` 無し。`batch --dry-run` は 470ms、stderr 空、`extract` も `run_book` も呼ばない（`batch.py:181-191` で continue。`dry_run` のとき `pipeline` を import しない）。実 51 冊 dry-run でもマニフェストは作られない。CLI `run --dry-run` は `pipeline.run_book` を呼ばないテストがある。 |
| 6. `read_books.py` は未変更。完了後フック無し。使い方は batch を別ステップと書く | PASS | `git rev-parse --is-inside-work-tree` は true。`git diff -- read_books.py` は空。`git status --porcelain -- read_books.py` は空。`read_books.py` に `batch` / `plan_books` / 完了後フックは無い。`docs/usage/13-semantica-books.md` 9-11 行は「`read_books.py` は変えない」「要約ができたあと、グラフ化は別ステップ」「完了後フックは無い」。 |
| 7. 品質ゲートは export でまだ走る | PASS_WITH_GAPS | `export_all`（`export_artifacts.py:325-372`）は `sanitize_export_payload` のあと `_assert_written_quality` → `assert_artifact_quality`。本番 `run_book` は必ず `export_all` を呼ぶ（`pipeline.py:276-284`）。Semantica venv でモック抽出の `run_book` に `patch(assert_artifact_quality)` を当てると `called=True`、`call_count=1`。ギャップ: `run_batch` のテストは `run_book_fn` を差し替え、ゲートを通さない。`accumulate_extract` だけ呼ぶとゲート無しでキャッシュを書ける。 |
| 8. テストはモックで列挙、skip、offset 再開、マニフェスト、Hermes 非書き込みを証明。ライブ xAI 無し | PASS_WITH_GAPS | 実装者のコマンドどおり `.venv` は `Ran 58 tests ... OK (skipped=3)`。Semantica venv の指定 4 モジュールは `Ran 24 tests ... OK`。`tests.test_book_semantica_batch` は 16 件すべて ok。AST で `batch.py` / `discover.py` の `import semantica` を拒否する。列挙、skip、`accumulate_extract` 再開、マニフェスト、Hermes ファイル拒否はテストがある。ライブ xAI は無い。破綻: fixture の冊キーは `ready.ocr` なのに `run_book_fn` をモックするため、本番の suffix 例外を検出できない。`--force` で `run_batch` が skip 冊を呼ぶテストは `should_skip_book` だけ。グラフ再構築と品質ゲートは batch テストに無い。 |
| 9. 使い方 `docs/usage/13-semantica-books.md` を更新した | PASS_WITH_GAPS | plan / batch / `--dry-run` / `--offset` / `--all-points` / `batch_state.json` / `extract_cache.json` / マニフェスト / `.venv` で plan、Semantica venv で batch がある。既定 80 と「黙って全コーパスへ LLM はかけない」と書いてある。破綻ではないが、88 行の `batch --book-key 採用入門.ocr` は上記 suffix バグで本番失敗する。 |
| 既定 `--limit` は `run` も `batch` も 80。全件は `--limit 0` または `--all-points` | PASS | `paths.DEFAULT_LIMIT` は 80。`parse_args(['run']).limit` は 80、`command` は `run`、`all_points` は False。`parse_args(['batch']).limit` は 80。`parse_args(['batch','--limit','0']).limit` は 0。200 件 fixture で既定 `RunConfig` の抽出は 80 件。そのあと `limit=0` は残り 120 件。黙って全件にはならない。 |
| 禁止: リポ venv の semantica、Hermes 書き込み、FAISS/Neo4j、`read_books.py` 変更 | PASS_WITH_GAPS | `.venv/bin/python -c "import semantica"` は `ModuleNotFoundError` exit 1。`book_semantica/` に `faiss` / `neo4j` は 0 件。Hermes exact パスは `ForbiddenOutputPath`。ギャップ: sibling は許可される（`assert_safe_output_path` は exact 一致だけ）。`SIBLING_ALLOWED /var/lib/happy/.local/state/hermes/book-graph-would-be-allowed.json`。Hermes ディレクトリ自体も許可。 |
| 単冊 `run` は既存グラフを skip しない | PASS | 実装者の注記どおり。`run_book` のソースに `should_skip_book` は無い。skip は `plan` / `batch` だけ。労務入門は `graph.json` があり `batch_state.json` も `extract_cache.json` も無い。`plan` は skip。単冊 `run` はキャッシュが無いので先頭から取り直して上書きする。 |
| CLI: `./scripts/run_book_semantica.sh plan` 対 `.venv python -m book_semantica plan` | PASS | どちらも exit 0、フッタ `pending=50 skip=1`、労務入門は skip。stdout 本体は一致。sh は Semantica venv（と bws）を使うので `import semantica` があっても落ちない。今回の `plan` 経路は semantica を import しない。`.venv` でも成功する。sh の stderr に bws の POSIX 名警告が 1 行ある。LLM は呼んでいない。 |

## ブロッカー

1. **`batch` が `.ocr` 冊の出力ディレクトリをファイルと誤認する。**
   `batch.py:198` が常に `output_dir=out` を渡し、`pipeline.py:56-59` が `Path.suffix` をファイル判定に使う。
   単冊 `run` は `output_dir=None` なので同じパスでも通る。
   使い方 88 行の `batch --book-key 採用入門.ocr` は壊れている。
   pending 50 のうち 4 冊が対象。
   テストは同じ `.ocr` fixture を `run_book_fn` モックで隠している。

## 品質ギャップ（FAIL の主因ではない）

1. 空または実体無しの `graph.json` でも skip する。失敗した書き出しを `--force` 無しでやり直せない。
2. `extract_cache.json` 欠落かつ `complete=false` のとき、済みスライスは再抽出しないが蓄積実体は消える。
3. 未完了の `batch` は CLI `--offset` を無視する。
4. Hermes の sibling パスと親ディレクトリは拒否されない。
5. `plan` の労務入門は `complete=True` かつ `next_offset=0`（状態ファイルが無いときの表示）。
6. マニフェスト success 行の `item_count` はチャンク長ではない。
7. `GraphBuilder(merge_entities=True)` がチャンク蓄積の実体数を畳む。
8. batch テストに `--force` の本番 `run_book`、品質ゲート、空グラフ、キャッシュ欠落が無い。

## 攻撃ごとの記録

### plan の再実行

```bash
.venv/bin/python -m book_semantica plan --repo-root /opt/AI-reads-books-page-by-page
```

exit 0。
フッタ `pending=50 skip=1`。
`skip	労務入門.ocr	2328	.../労務入門.ocr`。
保存済み plan-output との差分はコメント 4 行のみ。
本体は stale ではない。
`grep -c '^pending'` はフッタ `pending=50` を拾って 51 になる。冊行は 50 である。

労務入門の出力ディレクトリに `graph.json`（7945 bytes、entities 11、relationships 11）はある。
`batch_state.json` と `extract_cache.json` は無い。
skip はパイロット扱い（状態無し＋グラフ有り）である。

### テスト

リポ `.venv`（実装者の列挙、pipeline 無し）:

```
Ran 58 tests in 0.063s
OK (skipped=3)
```

pipeline を足すと `Ran 63`、`skipped=8`。
実装者の「58 OK skip 3」は、使い方に書いた集合では再現する。

Semantica venv（使い方の 4 モジュール）:

```
Ran 24 tests in 19.518s
OK
```

`tests.test_book_semantica_batch` は 16 ok。
再開テストは `accumulate_extract` までで、`run_book` / `build_graph` は通していない。
`test_batch_runs_only_missing_book_and_writes_manifest` は `run_book_fn` を差し替える。
fixture キー `ready.ocr` は本番経路なら suffix 例外になる。

### 再開、空グラフ、キャッシュ欠落、offset

すべて一時ディレクトリ。ライブ xAI 無し。

- 0 バイト `graph.json`: `has_graph=True`、`should_skip_book=True`
- `{"entities":[],"relationships":[]}`: skip
- `complete=false` かつ `graph.json` 有り: skip しない（再開対象）
- キャッシュ無し＋`next_offset=2`: 抽出は `命題C` `命題D` のみ。実体 id もその 2 つ。A/B は失われる
- キャッシュ有り: 2+2=4、2 回目は C/D のみ
- `_effective_offset(offset=0)` は未完了なら 2。`offset=3` も 2。`--force` なら 0

### `--dry-run`

```bash
.venv/bin/python -m book_semantica batch --dry-run --repo-root /opt/AI-reads-books-page-by-page
```

exit 0、約 470ms。
フッタ `pending=50 skip=1`。
実行前も実行後も `book_analysis/semantica/manifest.jsonl` は無い。
実装者の「dry-run はマニフェストを書かない」は成立する。

### Hermes

`--output-dir` に `semantica-knowledge-work.json` を渡すと `ForbiddenOutputPath`（exact）。
sibling の `book-graph-would-be-allowed.json` と親ディレクトリ `/var/lib/happy/.local/state/hermes` は `assert_safe_output_path` を通る。
書き込みはしていない。

### 既定 limit と `--limit 0`

既定 80。
200 件 fixture で既定は 80 件だけ抽出する。
`limit=0` は残り全部（covered_end 以降）。
黙って全コーパスにはならない。

### FAISS / Neo4j / semantica in venv / read_books.py

`book_semantica/` に faiss と neo4j の import は無い。
リポ `.venv` の `import semantica` は失敗。
`read_books.py` の git diff は空。

### CLI wrapper

```bash
./scripts/run_book_semantica.sh plan --repo-root /opt/AI-reads-books-page-by-page
```

exit 0。
`.venv` の plan と stdout 本体は一致。
semantica 不足では落ちない（Semantica venv を使う）。
`.venv -m book_semantica plan` も semantica 無しで成功する。

### 本番 `run_batch`（モック LLM、Semantica venv）

一時ディレクトリ。xAI は呼ばない。

```
AI_Agent_x_BPR success
採用入門.ocr fail output_dir must be a directory, not a file: .../採用入門.ocr
```

`_resolve_output_dir` に `output_dir=.../採用入門.ocr` を渡すと BLOCKED。
`output_dir=None` の単冊 `run_book` は同じキーで graph を書く。

品質ゲート: `assert_artifact_quality` は `run_book` から 1 回呼ばれる。

## 実装者の Status DONE について

| 実装者の数字 | 再実行 |
| --- | --- |
| plan pending=50 skip=1、労務入門 skip | 成立 |
| tests 58 OK skip 3（リポ venv） | 成立（pipeline 無しの集合） |
| 24 OK（Semantica venv） | 成立 |
| live batch 未実行、dry-run はマニフェストを書かない | 成立 |
| skip は plan/batch のみ。単冊 `run` は既存グラフを上書き | 成立 |
| キャッシュは `extract_cache.json` と `batch_state.json` | 成立 |

DONE を崩すのはテスト件数ではない。
本番 `batch` が `.ocr` 冊で失敗することである。

## 検証の範囲外

- 51 冊ライブ LLM
- Hermes グラフの作成
- 実装の修正
- リポ `.venv` への `pip install semantica`

## 実行したコマンド

```bash
.venv/bin/python -m book_semantica plan --repo-root /opt/AI-reads-books-page-by-page
.venv/bin/python -m book_semantica batch --dry-run --repo-root /opt/AI-reads-books-page-by-page
./scripts/run_book_semantica.sh plan --repo-root /opt/AI-reads-books-page-by-page
.venv/bin/python -m unittest tests.test_book_semantica_batch tests.test_book_semantica_paths \
  tests.test_book_semantica_load tests.test_book_semantica_quality \
  tests.test_book_semantica_quality_gate tests.test_book_semantica_xai
PYTHONPATH=/opt/AI-reads-books-page-by-page \
  /var/lib/happy/.local/share/semantica/venv/bin/python -m unittest \
  tests.test_book_semantica_xai tests.test_book_semantica_pipeline \
  tests.test_book_semantica_quality tests.test_book_semantica_quality_gate
.venv/bin/python -c "import semantica"
git diff -- read_books.py
git status --porcelain -- read_books.py
```

加えて、一時ディレクトリ上の Python プローブ（モック抽出のみ。ライブ xAI 無し）で skip、空グラフ、キャッシュ欠落、offset、dry-run マニフェスト、Hermes sibling、既定 80、`--limit 0`、本番 `run_batch` の `.ocr` 失敗を確認した。

## 検証ステータス

DONE
