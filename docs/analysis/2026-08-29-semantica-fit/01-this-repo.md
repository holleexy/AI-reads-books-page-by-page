# このリポジトリがすでにやっていること

このリポジトリの仕事は、本をページ単位で読み、学習可能な知識点を JSON に貯め、Markdown 要約を出すことである。
オントロジーやナレッジグラフは、成果物の定義に入っていない。

## 入口

動く入口は 3 つである。

| やりたいこと | 入口 |
| --- | --- |
| API が生きているか確かめる | `./run.sh smoke_test.py` |
| 1 冊以上の PDF を読む | `./run.sh read_books.py 本.pdf` |
| `kindle_pdfs/` の未処理 PDF を全部読む | `./run.sh run_all_books.py` |

上流の README は古い。
いまの手順は `docs/usage/` が正である。

## 入力までの経路

PDF の文字レイヤを `PyMuPDF` の `get_text()` で取る。
画像だけの PDF はほぼ全部ローカルスキップになる。

そのため、Kindle 本は次の経路で文字 PDF にする。

1. Windows の Kindle アプリでページをスクリーンショットする（`KindleCapture.bat`）
2. 画像をファイル名順で 1 つの PDF にする（`images_to_pdf.py`）
3. `ocrmypdf` と Tesseract で日本語 OCR する
4. `read_books.py` に渡す

Windows から Linux へは、Tailscale 経由の受け取り口がある。
PDF もページ画像の ZIP も同じ口で届き、届いたら OCR と全書読みに入る。

## 抽出そのもの

各ページを LLM に渡し、`PageContent` として次だけを取る。

```json
{
  "has_content": true,
  "knowledge": [
    "営業の本質は「他者からの共感獲得」であるという考え方"
  ]
}
```

目次、索引、奥付、空白、参考文献は捨てる。
本文、定義、議論、事例、結論、枠組みは知識点として追記する。
LLM 経路は xAI（API キーまたは OAuth）が先で、無ければ Cursor Agent SDK の `grok-4.6` である。

10 ページごと、および最終ページで JSON を原子的に書き出す。
途中失敗しても冊は止まらず、失敗ページ番号だけ `status.json` に残る。
バッチは区間要約を出さず、最終要約だけ出す。

新規抽出の知識点は `{"text", "page"}` である。
`page` は PDF の 1 始まりである。
LLM は文字列だけを返し、ページは抽出側が付ける。
詳細は [ページ番号は必須である](11-page-provenance.md) に書いた。

## いまある成果物

調査時点で、知識 JSON は 45 冊分ある。
知識点の合計は 88,205 件である。
調査時点の各件は文字列だけである。
それらの件にページ番号は付いていない。
エンティティ型、関係、出典リンクも付いていない。
新規抽出からページ番号が付く。
既存件へ後からページを復元することはしない。
既存件を取り直すこともしない。

出力の根は `book_analysis/` である。

| 場所 | 中身 |
| --- | --- |
| `knowledge_bases/{book_key}_knowledge.json` | 知識点の配列 |
| `knowledge_bases/{book_key}_status.json` | ページ数、失敗、完了時刻 |
| `summaries/{book_key}_final_NNN.md` | 最終要約 |
| `summaries/{book_key}_interval_NNN.md` | 区間要約（単冊実行時） |

1 冊は 1 つの JSON 配列である。
冊をまたいで同じ概念を束ねる処理はない。
近傍重複の除去もない。
『労務入門』では Arendt の三分法が、ほぼ同じ内容で複数件並んでいる。

## 明示的にやっていないこと

次はコードにも成果物にも存在しない。

- 型付きエンティティ（Person、Concept、Framework など）
- 関係（`労務 is_composed_of ルール` のような辺）
- クラスとプロパティのスキーマ（OWL、SHACL、SKOS）
- ノードと辺のグラフ、可視化、SPARQL や Cypher
- 冊をまたいだエンティティ解決
- 既存コーパス（文字列だけの知識点）から元ページへの復元
- ベクトル検索、GraphRAG、推論エンジン
