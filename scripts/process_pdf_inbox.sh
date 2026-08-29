#!/usr/bin/env bash
# Process PDFs dropped by the shared upload server into kindle_pdfs/_ready/.
set -euo pipefail
ROOT="/opt/AI-reads-books-page-by-page"
PDF_DIR="$ROOT/kindle_pdfs"
READY="$PDF_DIR/_ready"
DONE="$PDF_DIR/_ready/done"
FAIL="$PDF_DIR/_ready/failed"
LOGDIR="$ROOT/book_analysis/logs"
mkdir -p "$READY" "$DONE" "$FAIL" "$LOGDIR"
export PYTHONPATH="$ROOT/.ocr-deps${PYTHONPATH:+:$PYTHONPATH}"

process_pdf() {
  local marker="$1"
  local pdf name stem ocr log
  pdf="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1],encoding="utf-8"))["pdf"])' "$marker")"
  name="$(basename "$pdf")"
  stem="${name%.pdf}"
  ocr="$PDF_DIR/${stem}.ocr.pdf"
  log="$LOGDIR/pdf-inbox-${stem}-$(date +%Y%m%d-%H%M%S).log"
  echo "processing PDF $name" | tee -a "$log"
  if [[ ! -f "$pdf" ]]; then
    echo "missing $pdf" | tee -a "$log"
    return 1
  fi
  cd "$ROOT"
  if python3 -c 'import packaging' 2>/dev/null; then
    /usr/bin/ocrmypdf -l jpn+eng --skip-text --jobs 4 "$pdf" "$ocr" 2>&1 | tee -a "$log" \
      || cp -f "$pdf" "$ocr"
  else
    cp -f "$pdf" "$ocr"
  fi
  if ! bash run.sh read_books.py "$ocr" --interval 0 2>&1 | tee -a "$log"; then
    echo "read_books failed for $name" | tee -a "$log"
    return 1
  fi
  echo "finished PDF $name at $(date -Is)" | tee -a "$log"
}

echo "pdf inbox watcher started $(date -Is)"
while true; do
  shopt -s nullglob
  for marker in "$READY"/*.json; do
    [[ -f "$marker" ]] || continue
    base="$(basename "$marker")"
    if process_pdf "$marker"; then
      mv "$marker" "$DONE/$base"
    else
      mv "$marker" "$FAIL/$base"
      echo "failed PDF marker $base"
    fi
  done
  sleep 8
done
