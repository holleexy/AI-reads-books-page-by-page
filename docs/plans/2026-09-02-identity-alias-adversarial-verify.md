# 自己 same_as 本線の敵対検証

日付は 2026-09-02 である。
検証者は実装者ではない。報告は信用せず、コード・テスト・2冊の成果物・プロセスを自分で見た。
実装していない。コミットしていない。キューは止めていない。トークンは書いていない。

## Verdict

**PASS**

10項目はいずれも PASS である。
ゲートだけ無視して `graph.json` に自己辺を残す逃げ、`duplicates.json` への Product Owner / Accuracy Wall 手詰め、`read_books.py` 改変、リポ `.venv` への semantica 導入、優先キュー kill、51冊ライブは、見つからなかった。

## チェックリスト

### 1. 別名ペア列挙は単一関数。空 / None / source==target は別名ではない — PASS

`book_semantica/quality.py:199-213` の `iter_alias_pairs` が唯一の列挙である。

```199:213:book_semantica/quality.py
def iter_alias_pairs(relationships: list[dict] | None):
    """Yield distinct (source, target) pairs from alias relations.

    Empty, None, and source==target edges are not alias pairs.
    """
    for rel in relationships or []:
        rel_type = str(rel.get("type") or rel.get("predicate") or "")
        if rel_type not in ALIAS_RELATIONS:
            continue
        src, tgt = _rel_endpoints(rel)
        if not src or not tgt or src == "None" or tgt == "None":
            continue
        if src == tgt:
            continue
        yield src, tgt
```

端点は `_rel_endpoints`（`quality.py:193-196`）が `source`/`subject`、`target`/`object` を strip する。
空リストと `None` は `relationships or []` で回らない。
テスト: `AliasPairTests.test_empty_and_none_are_not_alias_pairs`、`test_self_loop_is_not_an_alias_pair`、`test_blank_and_none_endpoints_are_not_alias_pairs`。

### 2. collect_duplicates と assert_artifact_quality はその列挙だけを見る — PASS

`collect_duplicates` は `quality.py:274` で `list(iter_alias_pairs(relationships))` のみ。
旧インラインループ（`src and tgt` だけで自己辺を alias に入れる）は git diff で消えている。

`assert_artifact_quality` は `quality.py:383` に `frozenset({src, tgt})` が残る。
ただし入力は `iter_alias_pairs` の出力だけである。

```383:391:book_semantica/quality.py
    alias_pairs = [frozenset({src, tgt}) for src, tgt in iter_alias_pairs(relations)]
    if alias_pairs and not groups:
        raise QualityError(
            "duplicates.json is empty but graph has also_known_as/translated_as"
        )
    covered = [frozenset(group.get("members") or []) for group in groups]
    for pair in alias_pairs:
        if not any(pair <= group for group in covered):
            raise QualityError(f"alias pair {set(pair)} missing from duplicates.json")
```

自己辺は列挙時点で落ちるので、1要素集合 `{Product Owner}` は作られない。
本線が禁じたのは「自己辺を別名扱いする frozenset」であり、無向ペアの部分集合判定用の frozenset ではない。
`test_collect_duplicates_and_gate_use_only_iter_alias_pairs` が `iter_alias_pairs` を空に差し替えて両方を見ている。

### 3. 自己辺除去は ALIAS_RELATIONS に限らない — PASS

`drop_identity_edges`（`quality.py:216-224`）は type を見ない。strip 後に端点が等しければ落とす。

```216:224:book_semantica/quality.py
def drop_identity_edges(relationships: list[dict] | None) -> list[dict]:
    """Drop relations whose endpoints are the same after strip. All types."""
    kept: list[dict] = []
    for rel in relationships or []:
        src, tgt = _rel_endpoints(rel)
        if src == tgt:
            continue
        kept.append(rel)
    return kept
```

呼び出しは2箇所。

- `build_graph`（`graph.py:81`）: GraphBuilder の戻り値から落とす
- `sanitize_export_payload`（`export_artifacts.py:62`）: export / repair の両方

`test_drops_self_loops_of_any_relation_type` は `same_as` と `is_a` を落とし、`also_known_as(Labor, 労務)` を残す。
2冊の `graph.json` からも `is_a` / `related_to` 等の自己辺が消えている（後述）。

### 4. 自己 same_as だけのグラフは QualityError にならない — PASS

`test_self_same_as_only_does_not_raise`（`tests/test_book_semantica_quality.py:165-182`）が `same_as(Product Owner, Product Owner)` だけをゲートに渡し、例外なし。
検証者が unittest を再実行して OK。

### 5. Labor→労務 の also_known_as が duplicates 空なら QualityError — PASS

`test_raises_on_empty_duplicates_when_alias_exists`（同ファイル 149-163）。
検証者再実行で OK。コード上も `iter_alias_pairs` が `("Labor", "労務")` を出し、groups 空なら 385 行で落ちる。

### 6. read_books.py は未変更 — PASS

```
git diff --exit-code -- read_books.py
# exit 0
```

`git status --short -- read_books.py` も空。

### 7. テストはモック / フィクスチャ。ライブ xAI なし — PASS

追加テストはフィクスチャと `patch.object(quality, "iter_alias_pairs")`。
`test_build_graph_drops_identity_edges` は GraphBuilder をローカル呼び出しするだけ（`extract=False`）。xAI クライアントは無い。
`LiveArtifactGateTests` はディスク上の `労務入門.ocr` 成果物を読む skipUnless であり、LLM ではない。

### 8. 優先11冊キューは生きている。51冊ライブなし。リポ .venv に semantica なし — PASS

検証中もキューは動いていた。殺していない。

```
1800033  bash ./scripts/run_semantica_resume_queue.sh
1800154  python -m book_semantica batch --book-key … --limit 80
3869606  bash ./scripts/run_semantica_resume_queue.sh
1727463  bash ./scripts/run_semantica_resume_queue.sh   # 同時点でも生存
```

`--limit 80` の冊単位再開である。51冊一括ライブは見当たらない。
リポ `.venv` は `ModuleNotFoundError: No module named 'semantica'`。site-packages に semantica ディレクトリは無い。

### 9. 実装報告があり、トークンが無い — PASS

`docs/plans/2026-09-02-identity-alias-fix-report.md` が存在する。
`xai-` / `sk-` / `Bearer` / `api_key` / `XAI_API` は報告に無い。

### 10. FAIL だった2冊を repair。自己辺ゼロ。ゲート PASS。手詰めなし — PASS

検証者が Semantica venv で独立計測した。

| 冊 | graph.json 関係数 | source==target | extract_cache 自己辺（空でない端点） | assert_artifact_quality |
| --- | ---: | ---: | ---: | --- |
| 勝てるプロダクト開発の教科書 | 1309 | 0 | 2 | PASS |
| AI_Agent_x_BPR | 4861 | 0 | 13 | PASS |

報告の 1311→1309 / 4874→4861、キャッシュ残 2 と 13 と一致する。
mtime: 両冊の `graph.json` / `duplicates.json` / `ontology.owl` は 2026-09-02 18:44。`graph.html` と `extract_cache.json` は 12:52–12:54 のまま。repair が graph を書き、HTML とキャッシュは触っていない、という報告と一致する。

手詰めではない証拠:

- `collect_duplicates(graph.entities, graph.relationships)` の alias グループ集合と、ファイル上の alias グループ集合は両冊とも一致（勝てる 73=73 extra 0、AI 88=88 extra 0）
- singleton alias グループは 0
- `members == ["Product Owner"]` も `["Accuracy Wall"]` も無い
- AI の duplicates に Accuracy Wall 文字列は無い
- 勝てる duplicates の `Product Owner` ヒットは `Product Owner Involvement Level Map`（実在の `also_known_as` 相手）と exact_id `product owner`（小文字、件数 33 の既存衝突）。ゲートを通すための1要素別名グループではない

`book_semantica/` に冊名ハードコードのゲート skip は無い。

## Extra hunts

### ゲートだけ無視して graph.json に自己辺 — なし（FAIL にならず）

2冊とも identity_edges=0。`drop_identity would remove 0`。
ゲート skip-only ではない。

### repair_export は graph.json を書く — 書く

`export_artifacts.py:169-170` が `_write_json(..., graph)` する。sanitize が先に `graph["relationships"]` を置き換えるので、書いた中身は除去後である。
`test_repair_export_strips_identity_edges_from_graph_json` が `same_as` と `is_a` を落として1本残すことを固定している。

### graph.html は古い自己辺を含みうる — 注記。自動 FAIL ではない

報告が認めている。mtime は repair より約6時間前。Plotly 埋め込みで `relationships` キーは無い。
勝てる HTML に `same_as` ラベルが2件残る（エッジ type 配列）。`Product Owner` / `equally_dangerous_as` 文字列は HTML に無い（Plotly がノード名を別形式で持つ可能性はある）。
正本は `graph.json` であり、そこは自己辺 0。本線の捨てる案「ゲートだけ直して可視化が汚れたまま」は、repair が HTML を書き直さない範囲では残る。報告どおり。

### collect_duplicates が自己辺を union-find に入れない — 入れない

`iter_alias_pairs` 経由。`test_self_loop_does_not_create_alias_group`。
2冊の実グラフでも drop 後なので入力に自己辺が無い。

### 空白のみ ID、subject/object

`_rel_endpoints` は strip する。`"AI "` vs `"AI"` は `test_strips_before_comparing_endpoints` で落ちる。
空白のみは strip 後空になり、別名ではない。`drop_identity_edges` では空==空なのでグラフからも落ちる（端点欠損の辺も落とす。本線の「等しい端点」には含まれる）。
実2冊の関係キーは `source`/`target`/`type`。`subject`/`object` だけの辺は 0。type の前後空白も 0。

### 禁止ファイル

このスライスが触ってよいファイル以外で dirty なもの:

- `read_books.py`: 差分なし
- `docs/plans/2026-09-01-oauth-403-tasklist.md`: live 行が OAuth 再開の記録。identity-alias と無関係
- `scripts/run_semantica_newest_queue.sh`: `FORCE=1` で `--force` を渡せるようにした差分。identity-alias と無関係
- 走っている優先キューが他冊の `graph.json` 等を更新中（BtoB、業務設計、OE BPR ほか）

identity-alias 実装の git diff は許可ファイル7つに閉じる。他冊 graph をこのスライスが手で直した形跡は無い。

### キューは生存

上記 PID。`pending-priority-11.txt` に11冊が残っている。検証者は kill していない。

### extract_cache の自己辺

勝てる: `same_as(Product Owner, Product Owner)`、`equally_dangerous_as(product managers, product managers)`。
AI_Agent_x_BPR: 13本。`same_as(Accuracy Wall, Accuracy Wall)` のほか `is_a(ゼロトラスト, ゼロトラスト)` 等。
報告どおり未改修。次チャンクは `build_graph` / `sanitize_export_payload` を通る契約。今回の成功条件外。

### merge_duplicate_reports が古い groups を残しうる

repair は既存 `duplicates.json` と再計算分を merge する。原理上、手詰めグループが残る逃げがありうる。
今回の2冊は alias 集合が再計算と一致したので、その逃げは使われていない。

## Unittest

検証者が実行した。実装報告の 69 / 29 と一致する。

リポ `.venv`:

```
cd /opt/AI-reads-books-page-by-page
.venv/bin/python -m unittest tests.test_book_semantica_quality tests.test_book_semantica_quality_gate tests.test_book_semantica_batch tests.test_book_semantica_load -q
```

```
Ran 69 tests in 0.204s
OK
```

内訳（`def test_` の数）: quality 21、quality_gate 6、batch 30、load 12。

Semantica venv:

```
PYTHONPATH=/opt/AI-reads-books-page-by-page \
  /var/lib/happy/.local/share/semantica/venv/bin/python -m unittest \
  tests.test_book_semantica_quality tests.test_book_semantica_pipeline -q
```

```
Ran 29 tests in 18.004s
OK
```

内訳: quality 21 + pipeline 8。stderr に GraphBuilder / DuplicateDetector / ConflictDetector / KGVisualizer の Semantica 進捗が出る。失敗ではない。ライブ xAI 呼び出しは無い。

## git

```
git status --short -- book_semantica/quality.py book_semantica/graph.py book_semantica/export_artifacts.py tests/test_book_semantica_quality.py tests/test_book_semantica_quality_gate.py tests/test_book_semantica_pipeline.py docs/usage/13-semantica-books.md read_books.py
```

```
 M book_semantica/export_artifacts.py
 M book_semantica/graph.py
 M book_semantica/quality.py
 M docs/usage/13-semantica-books.md
 M tests/test_book_semantica_pipeline.py
 M tests/test_book_semantica_quality.py
 M tests/test_book_semantica_quality_gate.py
```

`read_books.py` は出ていない。

```
git diff --stat -- book_semantica/quality.py book_semantica/graph.py book_semantica/export_artifacts.py tests/test_book_semantica_quality.py tests/test_book_semantica_quality_gate.py tests/test_book_semantica_pipeline.py docs/usage/13-semantica-books.md read_books.py
```

```
 book_semantica/export_artifacts.py        |   4 ++
 book_semantica/graph.py                   |   6 +-
 book_semantica/quality.py                 |  54 ++++++++++-----
 docs/usage/13-semantica-books.md          |   8 ++-
 tests/test_book_semantica_pipeline.py     |  34 ++++++++++
 tests/test_book_semantica_quality.py      | 105 ++++++++++++++++++++++++++++++
 tests/test_book_semantica_quality_gate.py |  33 ++++++++++
 7 files changed, 223 insertions(+), 21 deletions(-)
```

HEAD は `7d4fb7c feat: refresh xAI OAuth before extract chunks die on 403`。この本線は未コミット。報告どおり。

## 独立に数えた自己辺（キャッシュ、graph.json）

勝てる `extract_cache.json` 自己辺 2:

- `same_as` Product Owner
- `equally_dangerous_as` product managers

AI_Agent_x_BPR `extract_cache.json` 自己辺 13（検証者が列挙）:

- `is_a` ゼロトラスト
- `increases_importance_of` ゼロトラスト
- `interacts_with` 技術レイヤー
- `related_to` AI（2本）
- `reduces_variability_of` AIエージェント
- `is_evaluation_axis_of` 業務標準化度
- `allows_conditional_transition_to` 柔軟なゲート制
- `balances` 柔軟なゲート制
- `contrasted_with` AI
- `referenced_as` プロンプトガイドライン
- `same_as` Accuracy Wall
- `part_of` 認証・権限管理

これらは `graph.json` には無い。ALIAS 以外も落ちている。

## FAIL 時の残欠陥

なし。
残るものは成功条件外（キャッシュ、HTML、大文字小文字が違う別実体、他冊の未 repair graph）であり、報告が既に書いている。
