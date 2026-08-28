# 使い方

このリポジトリは、PDF をページごとに読み、知識点を JSON に貯め、Markdown 要約を出す。

upstream の README は古い。
いま動く入口は次の 3 つである。

| やりたいこと | コマンド |
| --- | --- |
| API が生きているか確かめる | `./run.sh smoke_test.py` |
| PDF を読む | `./run.sh read_books.py 本.pdf` |
| `kindle_pdfs/` の未処理 PDF を全部読む | `./run.sh run_all_books.py` |

`run.sh` は Bitwarden Secrets Manager（`bws`）でキーを注入し、`.venv` のパッケージを載せて Python を起動する。
認証は `XAI_API_KEY`、Hermes の xAI OAuth、`CURSOR_API_KEY` の順である。

続きは用途別に分けた。

- [何をするか](01-what-it-does.md)
- [動かす前に揃えるもの](02-prerequisites.md)
- [1 冊を読む](03-single-book.md)
- [複数冊をバッチで読む](04-batch.md)
- [成果物と途中再開](05-outputs-and-resume.md)
- [設定一覧](06-config.md)
- [動かないとき](07-troubleshoot.md)
- [xAI OAuth](08-xai-oauth.md)
- [ローカル PDF の受け取り](10-local-upload.md)
- [スクリーンショットから PDF](11-screenshot-to-pdf.md)
- [Kindle 自動めくり](12-kindle-auto-screenshot.md)
