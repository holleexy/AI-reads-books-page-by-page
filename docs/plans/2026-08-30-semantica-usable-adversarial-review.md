# Semantica「使える状態」敵対的再検証

検証日は 2026-08-30 である。
検証者はこの実装を書いていない。
前回の Verdict は PASS_WITH_GAPS であり、実装側はギャップ修正と労務入門のライブ `--limit 3` 成功を主張した。
handoff 文書は証拠として使わず、コマンド再実行と成果物・テスト・コード読解で主張を崩した。
ブランチは `feat/semantica-books` である。
コミットも push もしていない。
実装の修正はしていない。
ライブ `--limit 3` 自体は再実行していない（xAI 呼び出しになるため）。
成果物の時刻・中身・問い合わせ・隔離だけを見た。

## Verdict

**PASS_WITH_GAPS**

「1冊の労務入門を `--limit 3` で回し、OWL・SHACL・グラフ・画面・問い合わせがリポ側に残り、Hermes 作業記録へ『労務入門』を書かない」は成立する。
前回のブロッカー（成果物不在、空 IRI、query の `graph not found`、OWL 判定が空クラスを通す、矛盾テスト不在、LLM 失敗時のパターン落下、provenance に book_key が無い）は、今回のコマンドでは崩せなかった。
残るのは品質ギャップである。
OWL の `rdfs:label` は英語クラス名である。
`duplicates.json` は空である。
ライブ `conflicts.json` は null id の confidence ノイズである。
SHACL に不正な `xsd:xsd:string` がある。
Hermes ファイルの SHA-256 は前回レビューと一致しないが、文字列 `労務入門` は含まれない。

「使える」の定義は、人が 09 の4項目と extra work を1冊で回せ、Hermes メモリを書かないことである。
その定義では FAIL ではない。
英語 OWL クラス名は、`ontology.json` と実体に日本語ラベルがあるので FAIL にしない。

## Claim-by-claim

| claim | result | evidence |
| --- | --- | --- |
| 1. 型付きエンティティと関係を LLM で取る（英語パターン NER ではない） | 成立（残ギャップあり） | `extract.py` は `NamedEntityRecognizer` / `RelationExtractor` を使わず `get_entity_method("llm")` と `get_relation_method("llm")` を `provider="xai"`、`silent_fail=False` で呼ぶ。失敗は `LLMExtractionError`。パターン結果は `extraction_method in {pattern, last_resort_pattern}` で拒否する。Semantica の `extract_entities_llm` は `silent_fail=False` で `ProcessingError` を上げ、pattern へ落ちない（inspect 済）。ライブ `graph.json` の metadata は `ner_method=llm`、`relation_method=llm`、`provider=xai`、`limit=3`。実体 metadata は `extraction_method=llm_typed`、`model=grok-4.6`。知識点先頭3件は英語混じりのレガシー文字列であり、実体も `Labor` と `労務` が並ぶ。これはソースの写しであり、パターン NER の証拠ではない。 |
| 2. 日本語の本要約から OWL と SHACL | 成立（残ギャップあり） | ライブ `ontology.owl` は 7428 bytes。`owl:Class rdf:about` は 28 件、空 IRI は 0、`rdf:about=""` は無い。例: `https://books.local/労務入門.ocr/LaborAffairs`。`ontology.json` の label は日本語である（「書籍」「労務」「人材マネジメント」「就業規則」）。`shapes.ttl` は 12547 bytes、`a sh:NodeShape` が 28 件、`sh:name "労務"` など。OWL 側の `rdfs:label` は `Book` / `LaborAffairs` で英語である。SHACL に `xsd:xsd:string` が 7 件ある。 |
| 3. ナレッジグラフを構築し、可視化し、問い合わせできる。本ファイルであり Hermes 8766 ではない | 成立 | ライブ `graph.json` は entities 11、relationships 11。`graph.html` は 4865266 bytes、`Plotly.newPlot` と `plotly-graph-div` があり、ノード text に `"Labor","\u52b4\u52d9"`（労務）が入る。プレースホルダ表ではない。`SEMANTICA_PYTHON` と `PYTHONPATH=/opt/AI-reads-books-page-by-page` で `query --book-key 労務入門.ocr --name 労務` は exit 0。近傍は `Labor`（also_known_as in）、`勤怠管理`、`給与計算`。`graph not found` ではない。`assert_viewer_port(8766)` は `PORT_REJECT_OK: port 8766 is the Hermes explorer; use 8767 for book graphs`。既定は 8767。`--dry-run` は使い方に「無い」と書いてある。 |
| 4. 意味的デデュープ、矛盾検出、出典（book_key、あれば page） | 部分 | `provenance.ttl` は `foaf:name "労務入門.ocr"` と `book:book_key "労務入門.ocr"` を持つ。page は無い。知識点先頭3件は文字列で `page=None` であり、欠落は想定どおり。`duplicates.json` は `{"candidates": [], "groups": []}`（39 bytes）。`graph.json` に `merged_from` は無い。`entity_resolution_applied: true` だけがマージの痕跡である。`--limit 3` で空の duplicates は、同一 id の重複が無ければ許容する。`conflicts.json` は1件あるが `entity_id: null`、`relationship_id: "None_None_focuses_on"` の confidence 衝突である。定義の食い違いではない。モックパイプラインは定義の食い違いで空でない conflicts を要求し、専用テスト `test_value_conflicts_are_detected` は矛盾 fixture で空なら落ちる。 |
| 5. xAI を Semantica に接続（`provider=xai`、base_url `https://api.x.ai/v1`） | 成立（登録＋ライブ痕跡） | Semantica venv の xAI テストは通過。ライブ実体は `provider=xai`、`model=grok-4.6`、`extraction_method=llm_typed`。キーの値は出していない。検証シェルでキーを print していない。 |
| 6. 本グラフは `book_analysis/semantica/`。Hermes `semantica-knowledge-work.json` へは書かない | 成立（SHA は前回と不一致） | 成果物は `book_analysis/semantica/労務入門.ocr/` にある。Hermes ファイルの SHA-256 は `d11529cc939841f7a76fd2afbf243805c4933cfd412ffc0a2992704961117596`。前回レビューの `2f7621ba93571979be49f4307b483aef178d2575d48ec77c5daa9345a9b88cc2` とは違う。`grep` で `労務入門` は 0 件。この検証は Hermes ファイルへ書いていない。同一ディレクトリの別ファイルはまだ許可される（`SIBLING_ALLOWED: .../hermes/book-graph-would-be-allowed.json`）。 |
| 7. このリポ `.venv` へ `pip install semantica` しない | 成立 | `.venv/bin/python -c "import semantica"` は `ModuleNotFoundError`、exit 1。`find_spec` は None。`requirements.txt` に semantica は無い。 |
| 8. 1冊既定、`--limit`、10万件の取り直しはしない | 成立 | 既定 `book_key` は `労務入門.ocr`、既定 `limit` は 80。ライブ metadata は `limit: 3`。知識点は 2328 件。全冊ループは `book_semantica/` に無い。 |
| 9. 労務入門のライブパイロットは走った | 成立 | 前回「成果物が無い」は偽になった。ディレクトリは 2026-08-30 10:13。`graph.json` の timestamp は `2026-08-30T10:13:31.782175`。検証者はパイプラインを再実行していない。成果物の中身はモック2クラス（労務 / 人材マネジメント）ではなく、28クラスのライブ OWL である。 |

## 必須コマンドの結果

現在ブランチは `feat/semantica-books` である。

ライブ成果物（bytes）は次である。

conflicts.json 479

duplicates.json 39

graph.html 4865266

graph.json 7945

ontology.json 14687

ontology.owl 7428

provenance.ttl 1438

shapes.ttl 12547

`ontology.owl` の `owl:Class rdf:about` は non-empty 28、empty 0 である。

`shapes.ttl` の `sh:NodeShape` は 28 である。

日本語ラベルの引用は次である。

`ontology.json`: `"label": "労務"`、`"label": "書籍"`、`"label": "人材マネジメント"`、`"comment"` 内の「人を生かして事をなす」。

実体: `"name": "労務"`、`"勤怠管理"`、`"給与計算"`、`"モグラ叩き"`。

`provenance.ttl` は `労務入門.ocr` と `book_key` を含む。

問い合わせ CLI は `graph not found` ではない。

Hermes JSON に `労務入門` は無い。

リポ `.venv` の unittest は 26 件、OK、skip 3 である。

Semantica venv の unittest は 8 件、OK である。

空 IRI スタブ `<owl:Class rdf:about="">` に対し `_owl_class_iris` は `[]` を返し、`assertGreaterEqual(len(iris), 1)` は落ちる。
ヘッダだけの OWL も同じである。
`assertNotIn('rdf:about=""', owl)` も空 about で落ちる。

矛盾 fixture（労務の definition が二つ）で `detect_conflicts` は空でない。
同一 definition では空である。
テストは空を通さない。

ポート 8766 は拒否された。

`import semantica` はリポ `.venv` で exit 1 である。

`book_semantica` / tests / scripts に実行指定の `method="pattern"` は無い。

## 攻撃が失敗したもの（実装が耐えた）

ライブ成果物が無い、は失敗した。
ディレクトリと8ファイルがある。

OWL のクラス IRI が空、は失敗した。
28 件すべて非空である。

`query` が `graph not found`、は失敗した。
`労務` の近傍が返る。

OWL テストが空 IRI を通す、は失敗した。
現行アサーションは空 about とヘッダ stub で落ちる。

矛盾テストが無い、は失敗した。
`test_value_conflicts_are_detected` があり、矛盾 fixture で空なら落ちる。

LLM 失敗時に英語パターンへ落ちる、は `extract.py` 経路では失敗した。
`get_entity_method("llm")` + `silent_fail=False` + `LLMExtractionError` + pattern metadata 拒否である。
`test_llm_failure_does_not_use_english_pattern_ner` は通過した。

Hermes ファイルへ『労務入門』を書いた、は失敗した。
文字列は 0 件である。

ポート 8766 は拒否された。

リポ `.venv` に semantica は入っていない。

`graph.html` が空プレースホルダ、は失敗した。
Plotly に11ノード分の text 配列がある。

## 攻撃が成功したもの（残ギャップ）

OWL のクラス表示名は英語である。
`rdfs:label` は `Book` / `LaborAffairs` であり、「書籍」「労務」ではない。
日本語は `ontology.json` の label と実体名と SHACL `sh:name` にある。
これはギャップであり FAIL 条件ではない。

`duplicates.json` は空である。
ライブグラフに `merged_from` が無い。
GraphBuilder のマージは unittest のモック（同一 id「労務」）では起きた。
`--limit 3` のライブでは同一 id 重複が無く、空ファイルは許容範囲である。

ライブ `conflicts.json` は定義矛盾ではない。
`None_None_focuses_on_confidence_conflict` は辺の confidence 0.95 と 0.88 を並べただけである。
extra work の「矛盾検出」はテストでは動く。
3点パイロットの成果物としては弱い。

SHACL のデータ型に `xsd:xsd:string` が7件ある。
これは不正な XSD である。
NodeShape が無い、という攻撃は失敗したが、形は壊れている。

Hermes SHA-256 は前回と違う。
『労務入門』は含まれないので、この本のパイプラインが書いた証拠にはならない。
別プロセスが同ファイルを更新した可能性は残る。
検証者は中身を dump していない。

`assert_safe_output_path` は Hermes のその1ファイルだけを拒否する。
同一ディレクトリの別ファイルは許可された。

知識点の先頭3件は英語本文である。
「Labor (労務) work commonly focuses on...」から英語実体が出るのは、抽出器が英語パターンへ落ちた証拠ではない。

モックパイプラインの `_fake_extract` は2タプルを返すため、テストは metadata に `ner_method` が無いことを要求する。
ライブ成果物には `ner_method` がある。
テストとライブの metadata 契約は一致していない。
これはテストの穴であり、ライブが llm と書いていない、という意味ではない。

## 前回「使える前に必要」だった項目の帰結

1. ライブ `--limit 3` の成果物がある。再実行はしていない。中身はライブ LLM と整合する。
2. 非空 `owl:Class rdf:about`、`sh:NodeShape`、日本語ラベル（json / 実体 / SHACL）を目視した。OWL の rdfs:label は英語のままである。
3. OWL 判定は非空 IRI 必須に変わった。空 stub で落ちることをコマンドで確認した。
4. `provenance.ttl` に `book_key` がある。page はレガシー文字列なので無い。
5. マージ後の page 復元コードはある。今回の3件は page を持たない。
6. LLM 失敗は pattern へ落ちない。metadata の `ner_method` はライブで `llm` である。
7. 矛盾検出テストがある。矛盾 fixture で空なら落ちる。
8. 成果物がある状態で問い合わせできる。無い状態で「問い合わせできる」とは使い方が書いていない。
9. `--dry-run` が無いこと、既定が `run` であることは `docs/usage/13-semantica-books.md` に書いてある。

## 検証しなかったこと

ライブ `--limit 3` のプロセスは見ていない。
成果物と metadata だけを見た。

`XAI_API_KEY` の値は出していない。
`bws run` がキーを注入するかは、値を出さない方針のため未確認である。

Plotly HTML をブラウザで開いてホバー操作はしていない。
ファイル内の `Plotly.newPlot` と text 配列だけを見た。

`serve --explorer` は未実行である。

既定 80 件の費用・品質・タイムアウトは測っていない。

10万件コーパス全体は実行していない。

Hermes explorer（8766）の稼働状態は見ていない。
拒否ロジックだけを見た。
