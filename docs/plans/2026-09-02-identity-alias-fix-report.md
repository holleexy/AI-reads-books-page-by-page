# 自己 same_as 本線の実装報告

日付は 2026-09-02 である。
コミットしていない。
ライブ LLM は回していない。
優先11冊のキューは止めていない。

## 何を変えたか

別名ペアの列挙を `book_semantica/quality.py` の `iter_alias_pairs` に一本化した。
空、`None`、source と target が等しい辺は別名ではない。
`collect_duplicates` と `assert_artifact_quality` は、この関数だけを見る。
ゲート側で `frozenset({src, tgt})` を独自に組んで自己辺を別名扱いすることはやめた。

自己辺の除去は `drop_identity_edges` である。
ALIAS_RELATIONS に限らず、関係一般について source と target が strip 後に等しい辺を落とす。
`build_graph` は GraphBuilder の戻り値から落とす。
`sanitize_export_payload` も同じ関数で `graph["relationships"]` を置き換える。
`repair_export` は除去後のグラフを `graph.json` へ書き戻す。
そうしないと、既存 graph.json の LLM なし repair がゲートで落ちたままになる。

## テスト件数

リポ `.venv`:

```
.venv/bin/python -m unittest tests.test_book_semantica_quality tests.test_book_semantica_quality_gate tests.test_book_semantica_batch tests.test_book_semantica_load -q
```

Ran 69 tests。OK。

内訳は quality 21、quality_gate 6、batch 30、load 12 である。

Semantica venv:

```
PYTHONPATH=/opt/AI-reads-books-page-by-page \
  /var/lib/happy/.local/share/semantica/venv/bin/python -m unittest \
  tests.test_book_semantica_quality tests.test_book_semantica_pipeline -q
```

Ran 29 tests。OK。

内訳は quality 21、pipeline 8 である。
`test_build_graph_drops_identity_edges` は GraphBuilder をライブ LLM なしで呼び、戻り値に自己辺が無いことを見ている。

固定した契約は次である。

- 自己 `same_as(Product Owner, Product Owner)` だけのグラフは QualityError にならない
- `also_known_as(Labor, 労務)` が duplicates に無いときは、いまどおり QualityError である
- `collect_duplicates` は自己辺から alias グループを作らない
- `iter_alias_pairs` を空に差し替えると、重複検出もゲートも別名を見ない
- `repair_export` は自己辺を `graph.json` から落とす
- `is_a(X, X)` のような別名以外の自己辺も落とす

## 2冊の repair

LLM なし、`--force` なし。
他冊の graph は触っていない。

```
PYTHONPATH=/opt/AI-reads-books-page-by-page \
  /var/lib/happy/.local/share/semantica/venv/bin/python -m book_semantica repair --book-key 勝てるプロダクト開発の教科書
PYTHONPATH=/opt/AI-reads-books-page-by-page \
  /var/lib/happy/.local/share/semantica/venv/bin/python -m book_semantica repair --book-key AI_Agent_x_BPR
```

| 冊 | repair 前の関係数 | 自己辺 | repair 後の関係数 | 自己辺 | 品質ゲート |
| --- | --- | --- | --- | --- | --- |
| 勝てるプロダクト開発の教科書 | 1311 | 2（`same_as(Product Owner, Product Owner)`、`equally_dangerous_as(product managers, product managers)`） | 1309 | 0 | PASS |
| AI_Agent_x_BPR | 4874 | 13（`same_as(Accuracy Wall, Accuracy Wall)` を含む。`is_a` や `related_to` などの自己辺も含む） | 4861 | 0 | PASS |

`assert_artifact_quality` は repair 後の成果物で通った。
duplicates.json に Product Owner や Accuracy Wall を手で足していない。
2冊だけゲートを外してもいない。

## 残るもの

`extract_cache.json` には、repair 前と同じ自己辺が残っている（勝てる 2、AI_Agent_x_BPR 13）。
次のチャンクは `build_graph` と `sanitize_export_payload` を通るので、組み直した `graph.json` には残らない。
キャッシュそのものは今回書いていない。

`repair_export` は `graph.html` を書き直さない。
画面は古い埋め込みグラフのままである。
問い合わせと品質ゲートの正本は `graph.json` である。

大文字小文字が違う別名（`Product Owner` と `product owner`）は、別名辺が両者を結んでいなければ別実体のままである。
今回の自己辺とは別の問題である。

他冊の `graph.json` に自己辺が残っていても、今回は触っていない。
再開バッチがそれらの冊を書き出すときは、同じ除去が走る。
