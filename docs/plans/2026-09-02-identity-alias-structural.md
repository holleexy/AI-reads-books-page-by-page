# 自己 same_as を品質ゲートで落とさないための本線

日付は 2026-09-02 である。
OAuth ではない。
『勝てるプロダクト開発の教科書』と `AI_Agent_x_BPR` が再開しても落ちる理由は、蓄積グラフに残った自己 `same_as` と、重複検出と品質ゲートの契約が食い違っていることである。

## 結論

別名関係の定義を一つに固定する。
**別名は、相異なる2つの実体IDを結ぶ辺だけである。**
自己辺 `same_as(X, X)` は別名ではない。グラフに残さない。
`collect_duplicates` と `assert_artifact_quality` は、同じ関数で別名ペアを列挙する。

これが本線である。
duplicates.json に `Product Owner` を手で足すこと、この2冊だけゲートを外すこと、ゲート側だけ自己辺を無視して graph.json に残すことは、いずれも対処である。

## いま壊れている契約

品質ゲートは次を要求する。
グラフが `also_known_as` / `translated_as` / `same_as` などを持つなら、その両端は `duplicates.json` のどれかのグループに含まれる。

意図は通っている。
Semantica の DuplicateDetector が別名辺を見ないので、こちらで別名を duplicate グループに載せ、書き出し後に突き合わせる。

しかし列挙の定義が二つある。

ゲートは `frozenset({source, target})` をそのまま見る。
source と target が同じだと、ペアは1要素 `{Product Owner}` になる。

重複検出の union-find は、メンバーが2未満のグループを捨てる。
自己辺はノードを1つ作るだけでグループにならない。

exact_id グループの `product owner`（小文字）は、`Product Owner` と文字列が違うので、1要素ペアの部分集合にもならない。

したがって、LLM か GraphBuilder が自己 `same_as` を1本でも出すと、抽出は成功し、書き出しのゲートだけが同じエラーで落ちる。
キャッシュにその辺が残るので、再開は何回でも同じ地点で死ぬ。

## 捨てる案

手で duplicates を直す。
次のスライスで別の自己 `same_as` が出れば、また落ちる。

ゲートだけ自己辺を無視する。
graph.json と可視化は汚れたままである。
クエリが `same_as` を辿ると自分自身に戻る。

自己辺を singleton グループとして duplicates に残す。
「重複」が1要素になり、exact_id の衝突（同じ id の実体が複数）と意味が混ざる。

プロンプトで自己 `same_as` を出さないよう頼む。
モデルは守らない。
ゲートの定義が割れたままである。

## 本線の置き方

別名ペアの列挙を `quality.py` に1関数置く。
空、`None`、source と target が等しい辺は、別名ではない。

`collect_duplicates` も `assert_artifact_quality` も、それ以外の別名辺だけを見る。
テストは「自己 `same_as` だけでは QualityError にならない」「`Labor` と `労務` の別名が duplicates に無いときは、いまどおり QualityError」の両方を固定する。

グラフの本線は `build_graph` の直後である。
GraphBuilder が自己辺を合成しても、書き出す relationships から source と target が等しい辺を落とす。
蓄積キャッシュから組み直すときも、同じ関数を通る。
`--force` も再抽出も要らない。
`repair` が既存 graph.json を通せば、止まっている2冊は LLM なしで直る。

関係一般について、自己辺は知識ではない。
別名以外の `is_a(X, X)` も同様に落とすのが、グラフとしての定義に揃う。
別名ゲートの再発だけを止めるなら、ALIAS_RELATIONS に限っても契約は閉じる。
本線は「関係は相異なる2端点を結ぶ」のほうである。

## 実装するときの範囲

触るのは `book_semantica/quality.py`、`book_semantica/graph.py`、対応テスト、必要なら `repair` の経路確認である。
`read_books.py` は触らない。
ライブ LLM は回さない。
優先キューは止めない。
2冊の修復は `repair`（LLM なし）で、本線が入ったあとでよい。

## 本線が入っても残るもの

大文字小文字が違う別名（`Product Owner` と `product owner`）は、別名辺が両者を結んでいれば duplicate グループになる。
結んでいなければ、別実体のままである。
それは今回の自己辺とは別の問題である。
