# Kindle をスクリーンショットして PDF にする

DeDRM は使わない。画面に出ているページを画像として撮り、PDF にまとめてからこのリポジトリで読む。

弁護士ではないので「法的にセーフ」とは言えない。DRM ファイルを解読する行為ではないが、著作物の複製そのものは残る。自分で買った本の個人利用でも、保証はできない。

## このツールが要求すること

`read_books.py` は各ページの **文字** を `get_text()` で取る。
スクリーンショットをそのまま繋いだ PDF は画像しか持たないので、ほぼ全部ローカルスキップになる。

必要な流れは次である。

1. ページ画像を撮る（Windows の Kindle アプリ）
2. 画像をファイル名順で 1 つの PDF にする
3. OCR して文字レイヤを乗せる
4. `./run.sh read_books.py` に渡す

## 1. 撮影

ページ順がファイル名で分かるようにする。例: `0001.png`, `0002.png`。
ウィンドウ全体ではなく本文領域だけ撮ると、OCR が楽である。
自動で Kindle をページ送りして撮るには、Windows で `scripts/kindle_capture.ps1` を使う。手順は [Kindle 自動めくり](12-kindle-auto-screenshot.md) である。

## 2. 画像を PDF にする

Linux 側に画像ディレクトリを置いたあと:

```bash
./run.sh images_to_pdf.py /path/to/pages -o kindle_pdfs/book.pdf
```

拡張子は `.png` `.jpg` `.jpeg` `.webp` `.tif` `.tiff`。名前の辞書順でページになる。

## 3. OCR

OSS の [ocrmypdf](https://github.com/ocrmypdf/OCRmyPDF) と Tesseract を使う。日本語なら `jpn` を付ける。

```bash
ocrmypdf -l jpn+eng --skip-text kindle_pdfs/book.pdf kindle_pdfs/book.ocr.pdf
```

`ocrmypdf` が無ければ入れない限り、このリポジトリは画像 PDF を本文として読めない。

## 4. 読む

```bash
./run.sh read_books.py kindle_pdfs/book.ocr.pdf --interval 0
```
