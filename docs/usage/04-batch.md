# 複数冊をバッチで読む

バッチ入口は `run_all_books.py` である。
`kindle_pdfs/` 直下の `*.pdf` を対象にし、完了済みを飛ばして並列処理する。

## 手順

1. `kindle_pdfs/` を作り、PDF を置く。
2. 並列数を変えるなら `MAX_BOOK_WORKERS` を付ける。既定は 2 である。
3. 起動する。

```bash
mkdir -p kindle_pdfs
# PDF を kindle_pdfs/ へコピーしたあと
MAX_BOOK_WORKERS=2 ./run.sh run_all_books.py
```

サブディレクトリは見ない。
拡張子は `.pdf` のみである。

## 完了判定

次のいずれかなら「済み」とみなして飛ばす。

- `book_analysis/knowledge_bases/{book_key}_status.json` があり、`summary_generated` が真かつ `test_mode` が偽
- その `book_key` の status が無く、`book_analysis/summaries/{book_key}_final_*.md` がある（旧データ向け）

`book_key` はファイル名から拡張子を除いた文字列である。
同名 PDF が複数あっても 1 件に潰す。

## バッチ固有の設定

各ワーカーは自分用の API クライアントを持つ。
`BookConfig` は `analysis_interval=None`、`test_pages=None` 固定である。
区間要約は出ない。全書を読む。

`run_all_books.py` は `.env` と `~/obsidian-work/.env` を読む。
`./run.sh` 経由なら `bws` 側のキーが優先されることが多い。
