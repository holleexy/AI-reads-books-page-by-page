# ローカル PDF の受け取り

Linux 側にファイルが無いときは、Windows PC から Tailscale 経由で `kindle_pdfs/` へ送る。

## 手順

1. `scripts/pdf_upload_server.py` を起動する。
2. 表示された URL を Windows のブラウザで開く。
3. Downloads の PDF を選んで送信する。
4. 揃ったら `./run.sh run_all_books.py` で全書処理する。

トークン無しの POST は拒否する。`kindle_pdfs/` は gitignore 済みである。
