# Kindle ページ画像の後続処理（2026-08-28）

Windows の `C:\Users\m3dp6\Downloads\kindle_pages` は Linux から直接読めない。
Tailscale の受け取り口に ZIP または PNG を送り、届いたら次を自動で走らせる。

1. `images_to_pdf.py` で 1 つの PDF にする
2. `ocrmypdf -l jpn+eng` で文字レイヤを乗せる
3. `read_books.py --interval 0` で全書を読む

成果物は `kindle_pdfs/` の OCR 済み PDF と `book_analysis/summaries/` の最終要約である。

2026-08-29：不完全な画面キャプチャで処理した『労務入門』は削除した。撮り直した画像が届いてから再処理する。

同じ受け取り口で PDF も送れる。PDF は `kindle_pdfs/` に保存し、`kindle_pdfs/_ready/` を見て全書処理する。
