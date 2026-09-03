#!/usr/bin/env bash
# Wait until 社内SE and 労務入門 batch processes exit, then resume the four FAIL books.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="${PWD}"
WATCH="${ROOT}/book_analysis/semantica/queue/wait-fail-4.log"
OUT="${ROOT}/book_analysis/semantica/queue/dispatcher-fail-4.out"

log() { echo "$(date -Iseconds) $*" | tee -a "${WATCH}"; }

keys_running() {
  python3 - <<'PY'
import subprocess
keys = [
    "社内SE1年目から貢献！-情シス-企画・開発・運用-107のルール_00.ocr",
    "労務入門.ocr",
]
out = subprocess.check_output(["ps", "-eo", "pid,cmd"], text=True)
live = []
for line in out.splitlines():
    if "extglob" in line or "dump_bash_state" in line or "sh -c" in line:
        continue
    if "venv/bin/python -m book_semantica batch --book-key" not in line:
        continue
    for k in keys:
        if k in line:
            live.append(k)
            break
print("\n".join(sorted(set(live))))
PY
}

log "wait for in-flight 社内SE and 労務入門"
while true; do
  live="$(keys_running || true)"
  if [[ -z "${live}" ]]; then
    log "in-flight extracts gone"
    break
  fi
  log "still: ${live//$'\n'/, }"
  sleep 20
done

python3 - <<'PY'
import subprocess, sys
out = subprocess.check_output(["ps", "-eo", "pid,cmd"], text=True)
for line in out.splitlines():
    if "extglob" in line or "dump_bash_state" in line:
        continue
    if "wait_then_resume" in line:
        continue
    if "run_semantica_resume_queue.sh" in line:
        print("dispatcher still alive: " + line, file=sys.stderr)
        sys.exit(2)
PY

export QUEUE="${ROOT}/book_analysis/semantica/queue/pending-fail-4.txt"
export MAX_JOBS=2
export LOAD_PAUSE=6
export MEM_MIN_KB=1500000
export LIMIT=80
export EXTRACT_CONCURRENCY=2
unset XAI_API_KEY || true
log "start fail-4 resume"
nohup ./scripts/run_semantica_resume_queue.sh >"${OUT}" 2>&1 &
log "fail-4 dispatcher pid=$! out=${OUT}"
