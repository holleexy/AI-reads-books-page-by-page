# 何をするか

PDF の各ページから本文を取り出し、LLM に知識点を抽出させる。
抽出結果は JSON に追記され、一定間隔または最後に Markdown 要約になる。

処理の単位は 1 冊である。
1 ページ失敗しても冊は止まらず、失敗ページ番号だけ記録する。

## 入口の違い

`read_books.py` は PDF パスを引数に取る入口である。
読むファイルは引数で渡す。既定は全書である。
試しに先頭だけ読むときは `--pages 60` を付ける。

`run_all_books.py` は `kindle_pdfs/*.pdf` を列挙し、完了済みを飛ばして並列処理する。
バッチでは区間要約を出さず、最終要約だけ出す。

`smoke_test.py` は `meditations.pdf` の 11 ページ目を 1 回だけ API に送り、抽出が空でないことを確認する。

## いまの LLM 経路

`XAI_API_KEY` があるときは xAI（`https://api.x.ai/v1`）の chat completions を使う。
キーが無くても Hermes の xAI OAuth があれば同じ端点を使う。
どちらも無いときは `CURSOR_API_KEY` で Cursor Agent SDK から `grok-4.6` を呼ぶ。
控えは `grok-4.5` である。
OmniRoute は使わない。
