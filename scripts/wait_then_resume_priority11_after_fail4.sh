#!/usr/bin/env bash
# After the fail-4 resume dispatcher exits, continue the remaining priority-11 books.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="${PWD}"
WATCH="${ROOT}/book_analysis/semantica/queue/wait-priority-11-after-fail4.log"
OUT="${ROOT}/book_analysis/semantica/queue/dispatcher-oauth-apply.out"
FAIL_PID="${1:?fail-4 dispatcher pid required}"

log() { echo "$(date -Iseconds) $*" | tee -a "${WATCH}"; }

log "wait for fail-4 dispatcher pid=${FAIL_PID}"
while kill -0 "${FAIL_PID}" 2>/dev/null; do
  sleep 20
done
log "fail-4 dispatcher gone"

python3 - <<'PY'
import subprocess, sys
out = subprocess.check_output(["ps", "-eo", "pid,cmd"], text=True)
for line in out.splitlines():
    if "extglob" in line or "dump_bash_state" in line:
        continue
    if "wait_then_resume" in line:
        continue
    if "run_semantica_resume_queue.sh" in line:
        print("another dispatcher still alive: " + line, file=sys.stderr)
        sys.exit(2)
PY

export QUEUE="${ROOT}/book_analysis/semantica/queue/pending-priority-11.txt"
export MAX_JOBS=2
export LOAD_PAUSE=6
export MEM_MIN_KB=1500000
export LIMIT=80
export EXTRACT_CONCURRENCY=2
unset XAI_API_KEY || true
log "start priority-11 resume"
nohup ./scripts/run_semantica_resume_queue.sh >>"${OUT}" 2>&1 &
log "priority-11 dispatcher pid=$!"
