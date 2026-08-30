# 品質ギャップの埋め方

日付は 2026-08-30 である。
対象は Semantica 本グラフの 4 点である。

## 原因

OWL の英語ラベルは、Semantica の `OWLExporter` が `label` ではなく `name` を `rdfs:label` に書くためである。
`ontology.json` には日本語 `label` がある。

`duplicates.json` が空なのは、検出をマージ後のノードにかけ、かつ `also_known_as` / `translated_as` を見ていないためである。
`--limit 3` のグラフには Labor/労務、勤怠管理、給与計算、モグラ叩きの別名辺がある。

`conflicts.json` の null id は、関係の confidence 差を `None_None_focuses_on` として出しているためである。
定義の食い違いではない。

`xsd:xsd:string` は、range がすでに `xsd:string` のところへ SHACLGenerator がもう一度 `xsd:` を付けるためである。

## 直したこと

自前の OWL 書き出しで `rdfs:label` に日本語 `label` を使い、`xml:lang="ja"` を付ける。
IRI は従来どおり ASCII の `name` である。
SHACL は書き出し後に `xsd:xsd:` を `xsd:` へ畳む。
重複は同一 id と別名辺からグループを作る。
矛盾は confidence と `None_None` を捨てる。
次回のクラス推定プロンプトは、label と comment を日本語、range を `xsd:string` 一度だけ、と明示する。

ライブ成果物は LLM を再実行せず `repair` で直せる。

```bash
./scripts/run_book_semantica.sh repair --book-key 労務入門.ocr
```

書き出しの出口は毎回 `sanitize_export_payload` と `assert_artifact_quality` を通る。
呼び出し元が直しを忘れても、4 点はファイルに残さない。
詳細は [品質ギャップを再発させない出口](2026-08-30-quality-recurrence-gate.md) である。
