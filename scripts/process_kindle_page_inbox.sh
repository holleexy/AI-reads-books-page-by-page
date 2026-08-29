#!/usr/bin/env bash
# Process each kindle_pages/<book>/ inbox: PDF -> OCR -> read_books.py.
# Same receive URL can hold multiple zips; each zip name is a folder.
set -euo pipefail
ROOT="/opt/AI-reads-books-page-by-page"
INBOX="$ROOT/kindle_pages"
LOGDIR="$ROOT/book_analysis/logs"
mkdir -p "$INBOX" "$ROOT/kindle_pdfs" "$LOGDIR"

export PYTHONPATH="$ROOT/.ocr-deps${PYTHONPATH:+:$PYTHONPATH}"

process_book() {
  local dir="$1"
  local name
  name="$(basename "$dir")"
  local pdf="$ROOT/kindle_pdfs/${name}.pdf"
  local ocr="$ROOT/kindle_pdfs/${name}.ocr.pdf"
  local log="$LOGDIR/inbox-${name}-$(date +%Y%m%d-%H%M%S).log"
  echo "processing $name" | tee -a "$log"
  cd "$ROOT"
  bash run.sh images_to_pdf.py "$dir" -o "$pdf" 2>&1 | tee -a "$log"
  if ! python3 -c 'import packaging' 2>/dev/null; then
    echo "packaging is missing; OCR cannot start" | tee -a "$log"
    return 1
  fi
  /usr/bin/ocrmypdf -l jpn+eng --skip-text --jobs 4 "$pdf" "$ocr" 2>&1 | tee -a "$log"
  if ! bash run.sh read_books.py "$ocr" --interval 0 2>&1 | tee -a "$log"; then
    echo "read_books failed for $name" | tee -a "$log"
    return 1
  fi
  python3 - "$dir" "$name" "$ocr" <<'PY'
import json, sys
from datetime import datetime, timezone
from pathlib import Path
dir_path, name, ocr = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
payload = {
    "name": name,
    "ocr": ocr,
    "finished_at": datetime.now().astimezone().isoformat(),
    "ok": True,
}
(dir_path / "_processed.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
PY
  echo "finished $name at $(date -Is)" | tee -a "$log"
}

echo "inbox watcher started $(date -Is)"
while true; do
  shopt -s nullglob
  for dir in "$INBOX"/*/; do
    [[ -d "$dir" ]] || continue
    [[ -f "${dir}_ready.json" ]] || continue
    [[ -f "${dir}_processed.json" ]] && continue
    [[ -f "${dir}_failed.json" ]] && continue
    if ! process_book "${dir%/}"; then
      echo "{\"ok\": false, \"at\": \"$(date -Is)\"}" > "${dir}_failed.json"
      echo "failed $(basename "$dir")"
    fi
  done
  sleep 8
done
