# 成果物と途中再開

出力の根は `book_analysis/` である。

| 場所 | 中身 |
| --- | --- |
| `pdfs/` | 入力 PDF のコピー。同名でサイズが違うときは hash 付きに改名する |
| `knowledge_bases/{book_key}_knowledge.json` | 抽出した知識点の配列 |
| `knowledge_bases/{book_key}_progress.json` | 再開用。完了後に削除 |
| `knowledge_bases/{book_key}_status.json` | ページ数、失敗ページ、完了時刻 |
| `summaries/{book_key}_interval_NNN.md` | 区間要約。バッチでは作らない |
| `summaries/{book_key}_final_NNN.md` | 最終要約。再実行のたびに番号が増える |

`pdfs/`、`*_progress.json`、`*_status.json`、区間要約は git に乗らない。
知識 JSON と最終要約は追跡対象である。

## 知識 JSON の形

新規抽出は命題とページ番号を対で書く。
`page` は PDF の 1 始まりである。
ログの `Processing page N` と同じ番号である。
ページ番号は LLM に推測させない。
抽出側が処理中のページを付ける。

```json
{
  "knowledge": [
    {
      "text": "営業の本質は「他者からの共感獲得」であるという考え方",
      "page": 12
    }
  ]
}
```

旧形式（文字列だけの配列）は読込時に `{"text": "...", "page": null}` になる。
途中再開すると、旧件は `null`、新規件は番号付きで混在する。
混在は許容する。
既存の約 10 万件をページのために取り直すことはしない。
詳細は [既存コーパスは取り直さない](../analysis/2026-08-29-semantica-fit/12-no-full-reextract.md) に書いた。

10 ページごと、および最終ページで原子的に書き出す。

## 再開

`process_book()` は既存の knowledge を読み、progress の `last_page` 以降だけ処理する。
同じ PDF を途中からやり直すときは、progress を残したまま再実行すればよい。
途中再開では、すでに貯まっている旧件の `page` は埋まらない。

最初からやり直すときは、その `book_key` の knowledge、progress、status を消す。
最終要約ファイルが残っていると、バッチは legacy 判定で飛ばすことがある。
その場合は該当する `*_final_*.md` も退ける。

## 失敗ページ

API 失敗や JSON パース失敗は `failed_pages` にページ番号（0 始まり）が入る。
冊全体は継続する。
status の `completed_at` は最終要約が書けてから付く。
