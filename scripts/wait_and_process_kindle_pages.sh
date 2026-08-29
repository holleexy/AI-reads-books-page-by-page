#!/usr/bin/env bash
# Wait for uploaded Kindle page images, then PDF -> OCR -> read_books.py.
set -euo pipefail
ROOT="/opt/AI-reads-books-page-by-page"
DIR="$ROOT/kindle_pages"
PDF="$ROOT/kindle_pdfs/kindle_pages.pdf"
OCR="$ROOT/kindle_pdfs/kindle_pages.ocr.pdf"
LOG="$ROOT/book_analysis/logs/kindle-pages-$(date +%Y%m%d-%H%M%S).log"
mkdir -p "$DIR" "$ROOT/kindle_pdfs" "$ROOT/book_analysis/logs"

image_count() {
  find "$DIR" -maxdepth 1 -type f \( -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.webp' -o -iname '*.tif' -o -iname '*.tiff' -o -iname '*.bmp' \) | wc -l
}

echo "waiting for kindle_pages images in $DIR" | tee -a "$LOG"
prev=-1
stable=0
for i in $(seq 1 720); do
  n="$(image_count)"
  echo "$(date -Is) images=$n" | tee -a "$LOG"
  if [[ "$n" -ge 3 ]]; then
    if [[ "$n" -eq "$prev" ]]; then
      stable=$((stable + 1))
    else
      stable=0
    fi
    if [[ "$stable" -ge 3 ]]; then
      echo "images settled at $n" | tee -a "$LOG"
      break
    fi
  fi
  prev="$n"
  if [[ "$i" -eq 720 ]]; then
    echo "timed out waiting for images" | tee -a "$LOG"
    exit 1
  fi
  sleep 5
done

cd "$ROOT"
echo "building PDF" | tee -a "$LOG"
bash run.sh images_to_pdf.py "$DIR" -o "$PDF" 2>&1 | tee -a "$LOG"

echo "OCR" | tee -a "$LOG"
export PYTHONPATH="$ROOT/.ocr-deps${PYTHONPATH:+:$PYTHONPATH}"
if ! python3 -c 'import packaging' 2>/dev/null; then
  echo "packaging is missing; OCR cannot start" | tee -a "$LOG"
  exit 1
fi
/usr/bin/ocrmypdf -l jpn+eng --skip-text --jobs 4 "$PDF" "$OCR" 2>&1 | tee -a "$LOG"

echo "reading book" | tee -a "$LOG"
bash run.sh read_books.py "$OCR" --interval 0 2>&1 | tee -a "$LOG"
echo "finished at $(date -Is)" | tee -a "$LOG"
ls -l "$ROOT/book_analysis/summaries/"*kindle_pages* 2>/dev/null | tee -a "$LOG" || true
