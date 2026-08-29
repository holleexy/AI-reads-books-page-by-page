# ローカル PDF の受け取り

Linux 側にファイルが無いときは、Windows PC から Tailscale 経由で送る。
PDF もページ画像の ZIP も、同じ受け取り口でよい。

## 手順

1. 受け取りページを Windows のブラウザで開く。
2. PDF、またはページ画像の ZIP を選んで送信する。
3. 届いたファイルは自動で OCR（必要なとき）と全書読みに入る。

ZIP は本ごとにファイル名を変える。`0001.png` が混ざらない。
トークン無しの POST は拒否する。`kindle_pdfs/` は gitignore 済みである。
