# 自己 same_as 本線の handoff

日付は 2026-09-02 である。
オーケストレーターがサブエージェントへ委譲する。
実装はコミットしない。push しない。
ライブ LLM は回さない。`--force` しない。`--all-points` しない。
優先11冊のキューは止めない。
リポ `.venv` へ semantica を入れない。Hermes 作業記録に書かない。

判断の根拠は [自己 same_as を品質ゲートで落とさないための本線](2026-09-02-identity-alias-structural.md) である。

## ゴール

別名関係の定義を一つにする。
別名は相異なる2つの実体IDを結ぶ辺だけである。
自己辺はグラフに残さない。
`collect_duplicates` と `assert_artifact_quality` は同じ列挙を使う。

## 成功条件

1. `book_semantica/quality.py` に別名ペア列挙の単一関数がある（名前は実装者に任せる）。空、`None`、source と target が等しい辺は別名ではない。
2. `collect_duplicates` と `assert_artifact_quality` はその関数だけを見る。ゲート側で `frozenset({src, tgt})` を独自に組んで自己辺を別名扱いしない。
3. `build_graph` の戻り値から、source と target が等しい関係を落とす。ALIAS_RELATIONS に限らず、関係一般の自己辺を落とす（本線「関係は相異なる2端点」）。
4. 自己 `same_as(X, X)` だけのグラフは `assert_artifact_quality` が QualityError を上げない。
5. `also_known_as` で `Labor` と `労務` が結ばれ、duplicates にそれが無いときは、いまどおり QualityError である。
6. `read_books.py` は変えない。
7. テストはモックまたはフィクスチャ。ライブ xAI は不要。
8. 優先キューを kill しない。51冊ライブを回さない。
9. 実装報告を `docs/plans/2026-09-02-identity-alias-fix-report.md` に書く。トークンは書かない。
10. テストが通ったあと、止まっている2冊（`勝てるプロダクト開発の教科書`、`AI_Agent_x_BPR`）を LLM なし `repair` する。repair 後の graph.json に当該自己 `same_as` が無く、`assert_artifact_quality` が通る。走っている他冊の graph は触らない。

## 触ってよいファイル

- `book_semantica/quality.py`
- `book_semantica/graph.py`
- `book_semantica/export_artifacts.py`（repair 経路が自己辺を残すなら）
- `tests/test_book_semantica_quality.py`
- `tests/test_book_semantica_quality_gate.py`（必要なら）
- `docs/usage/13-semantica-books.md`（品質ゲートの1段落。必要なら）
- `docs/plans/2026-09-02-identity-alias-fix-report.md`

repair 対象の既存成果物:

- `book_analysis/semantica/勝てるプロダクト開発の教科書/`
- `book_analysis/semantica/AI_Agent_x_BPR/`

## 禁止

- duplicates.json に名前を手で足してゲートを通す
- 2冊だけゲートを無効化する
- ゲート側だけ無視して graph.json に自己辺を残す
- ライブ `batch` / `--force` / `--all-points`
- FAISS / Neo4j
- Semantica の pip install
- 走っている優先11冊キューの kill
- `read_books.py`

## 検証コマンド

リポ `.venv`:

```bash
.venv/bin/python -m unittest tests.test_book_semantica_quality tests.test_book_semantica_quality_gate tests.test_book_semantica_batch tests.test_book_semantica_load -q
```

Semantica venv（graph.py が GraphBuilder を import する）:

```bash
PYTHONPATH=/opt/AI-reads-books-page-by-page \
  /var/lib/happy/.local/share/semantica/venv/bin/python -m unittest \
  tests.test_book_semantica_quality tests.test_book_semantica_pipeline -q
```

repair 後の証拠（トークン無し、自己辺の有無だけ）:

```bash
PYTHONPATH=/opt/AI-reads-books-page-by-page \
  /var/lib/happy/.local/share/semantica/venv/bin/python - <<'PY'
# 2冊の graph に source==target の辺が無いこと、assert_artifact_quality が通ることを印字
PY
```
