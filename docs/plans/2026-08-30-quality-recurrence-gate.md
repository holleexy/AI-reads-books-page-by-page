# 品質ギャップを再発させない出口

日付は 2026-08-30 である。
対象は OWL 英語ラベル、空の duplicates、confidence 矛盾ノイズ、`xsd:xsd:` の 4 点である。

## なぜ直しただけでは足りないか

前回の直しは、品質関数を呼ぶ側が忘れなければ効く。
`export_all` が呼び出し元の duplicates / conflicts をそのまま書く経路が残っていた。
`write_owl` の英語フォールバックと、SHACL フォールバックで `fix_shacl_datatypes` を呼ばない経路も残っていた。

呼び出し元が Semantica の `OWLExporter` やマージ後だけの DuplicateDetector に戻すと、同じすきまが戻る。

## いまの出口

書き出しは必ず次を通る。

1. `sanitize_export_payload` が日本語オントロジー正規化、別名辺からの重複、矛盾フィルタをやり直す。
2. `write_owl` は `quality.render_owl` だけを使う。`OWLExporter` は import しない。
3. `render_shacl` は generator 成功時も失敗時も `fix_shacl_datatypes` を通す。
4. ファイルを書いたあと `assert_artifact_quality` が 4 点を検査する。違反は `QualityError` で止まる。

`repair` も同じ出口である。既存の `duplicates.json` とグラフ上の別名辺を合流する。

## 検査が落とすもの

- SHACL に `xsd:xsd:` がある
- クラスに日本語 `label` があるのに OWL の `rdfs:label` が英語 `name` である
- グラフに `also_known_as` / `translated_as` があるのに `duplicates.json` が空、またはその組が無い
- `conflicts.json` に `property_name=confidence` または `None_None` の null id が残る

## テスト

リポジトリの `.venv` で、品質関数と出口の両方を見る。

```bash
.venv/bin/python -m unittest \
  tests.test_book_semantica_quality \
  tests.test_book_semantica_quality_gate \
  tests.test_book_semantica_load \
  tests.test_book_semantica_paths
```
