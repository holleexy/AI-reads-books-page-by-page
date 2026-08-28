#!/usr/bin/env bash
# Wait until the three expected PDFs are in kindle_pdfs, then process them.
set -euo pipefail
ROOT="/opt/AI-reads-books-page-by-page"
DIR="$ROOT/kindle_pdfs"
LOG="$ROOT/book_analysis/logs/batch-$(date +%Y%m%d-%H%M%S).log"
mkdir -p "$ROOT/book_analysis/logs"

expected=(
  "エンジニアのための自己管理入門.pdf"
  "プロダクトマネジメントのすべて.pdf"
  "法人営業勝ちパターン大全.pdf"
)

echo "waiting for PDFs in $DIR" | tee -a "$LOG"
for i in $(seq 1 360); do
  missing=0
  for name in "${expected[@]}"; do
    if [[ ! -f "$DIR/$name" ]]; then
      missing=1
    fi
  done
  if [[ "$missing" -eq 0 ]]; then
    echo "all PDFs received at $(date -Is)" | tee -a "$LOG"
    ls -l "$DIR"/*.pdf | tee -a "$LOG"
    cd "$ROOT"
    MAX_BOOK_WORKERS=2 bash run.sh run_all_books.py 2>&1 | tee -a "$LOG"
    echo "batch finished at $(date -Is)" | tee -a "$LOG"
    exit 0
  fi
  sleep 5
done
echo "timed out waiting for PDFs" | tee -a "$LOG"
exit 1
