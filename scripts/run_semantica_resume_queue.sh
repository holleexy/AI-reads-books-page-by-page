#!/usr/bin/env bash
# Resume incomplete book graphs until complete=true. Does not write Hermes.
# Skips a book only when batch_state.complete is true, or it failed this run.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="${PWD}"
QUEUE="${QUEUE:-${ROOT}/book_analysis/semantica/queue/pending-priority-11.txt}"
RUN_DIR="${ROOT}/book_analysis/semantica/queue/run-$(date +%Y%m%d-%H%M%S)"
LOG_DIR="${RUN_DIR}/logs"
mkdir -p "${LOG_DIR}"
MAX_JOBS="${MAX_JOBS:-2}"
LOAD_PAUSE="${LOAD_PAUSE:-6}"
MEM_MIN_KB="${MEM_MIN_KB:-1500000}"
LIMIT="${LIMIT:-80}"
EXTRACT_CONCURRENCY="${EXTRACT_CONCURRENCY:-2}"
export EXTRACT_CONCURRENCY

if [[ ! -f "${QUEUE}" ]]; then
  echo "missing queue: ${QUEUE}" >&2
  exit 1
fi

echo "run_dir=${RUN_DIR}"
echo "max_jobs=${MAX_JOBS} load_pause=${LOAD_PAUSE} mem_min_kb=${MEM_MIN_KB} limit=${LIMIT} extract_concurrency=${EXTRACT_CONCURRENCY} resume=1"
cp "${QUEUE}" "${RUN_DIR}/queue.txt"
: > "${RUN_DIR}/done.txt"
: > "${RUN_DIR}/fail.txt"
: > "${RUN_DIR}/pids.txt"

book_already_running() {
  local want="$1"
  pgrep -af 'python -m book_semantica batch --book-key ' | grep -F -- "${want}" | grep -v grep >/dev/null 2>&1
}

book_complete() {
  local key="$1"
  python3 - "${ROOT}" "${key}" <<'PY'
import json, sys
from pathlib import Path
root, key = Path(sys.argv[1]), sys.argv[2]
path = root / "book_analysis" / "semantica" / key / "batch_state.json"
if not path.is_file():
    raise SystemExit(1)
try:
    state = json.loads(path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    raise SystemExit(1)
raise SystemExit(0 if isinstance(state, dict) and state.get("complete") else 1)
PY
}

book_failed() {
  local key="$1"
  [[ -s "${RUN_DIR}/fail.txt" ]] && grep -Fxq -- "${key}" "${RUN_DIR}/fail.txt"
}

wait_for_slot() {
  local running load1 mem_avail wpid wrest alive
  while true; do
    running=0
    alive=""
    if [[ -s "${RUN_DIR}/pids.txt" ]]; then
      while read -r wpid wrest || [[ -n "${wpid:-}" ]]; do
        [[ -z "${wpid:-}" ]] && continue
        if kill -0 "${wpid}" 2>/dev/null; then
          alive+="${wpid} ${wrest}"$'\n'
          running=$((running + 1))
        fi
      done < "${RUN_DIR}/pids.txt"
      printf '%s' "${alive}" > "${RUN_DIR}/pids.txt"
    fi
    load1="$(awk '{print $1}' /proc/loadavg < /dev/null)"
    mem_avail="$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)"
    echo "$(date -Iseconds) running=${running} load1=${load1} mem_avail_kb=${mem_avail}" >> "${RUN_DIR}/load.log"
    if (( running < MAX_JOBS )); then
      awk -v l="${load1}" -v pause="${LOAD_PAUSE}" 'BEGIN { exit (l+0 >= pause+0) ? 1 : 0 }' </dev/null \
        && (( mem_avail >= MEM_MIN_KB )) && return 0
    fi
    sleep 20
  done
}

running_count() {
  local running=0 wpid wrest
  if [[ -s "${RUN_DIR}/pids.txt" ]]; then
    while read -r wpid wrest || [[ -n "${wpid:-}" ]]; do
      [[ -z "${wpid:-}" ]] && continue
      if kill -0 "${wpid}" 2>/dev/null; then
        running=$((running + 1))
      fi
    done < "${RUN_DIR}/pids.txt"
  fi
  echo "${running}"
}

pending_count=1
while (( pending_count > 0 )); do
  pending_count=0
  while IFS= read -r key || [[ -n "${key}" ]]; do
    [[ -z "${key}" ]] && continue
    if book_failed "${key}"; then
      continue
    fi
    if book_complete "${key}"; then
      if ! grep -Fxq -- "${key}" "${RUN_DIR}/done.txt" 2>/dev/null; then
        echo "${key}" >> "${RUN_DIR}/done.txt"
        echo "$(date -Iseconds) COMPLETE ${key}" | tee -a "${RUN_DIR}/progress.txt"
      fi
      continue
    fi
    pending_count=$((pending_count + 1))
    if book_already_running "${key}"; then
      continue
    fi
    wait_for_slot
    log="${LOG_DIR}/${key}.log"
    echo "$(date -Iseconds) START ${key}" | tee -a "${RUN_DIR}/progress.txt"
    (
      set +e
      "${ROOT}/scripts/run_book_semantica.sh" batch --book-key "${key}" --limit "${LIMIT}" >>"${log}" 2>&1
      rc=$?
      if [[ ${rc} -eq 0 ]]; then
        echo "$(date -Iseconds) OK ${key} rc=${rc}" >> "${RUN_DIR}/progress.txt"
      else
        echo "$(date -Iseconds) FAIL ${key} rc=${rc}" >> "${RUN_DIR}/progress.txt"
        echo "${key}" >> "${RUN_DIR}/fail.txt"
      fi
      exit ${rc}
    ) &
    echo "$! ${key}" >> "${RUN_DIR}/pids.txt"
  done < "${RUN_DIR}/queue.txt"

  if (( pending_count == 0 )); then
    break
  fi
  if (( $(running_count) > 0 )); then
    sleep 20
  else
    sleep 5
  fi
done

wait
echo "$(date -Iseconds) ALL_DONE" | tee -a "${RUN_DIR}/progress.txt"
echo "done=$(wc -l < "${RUN_DIR}/done.txt") fail=$(wc -l < "${RUN_DIR}/fail.txt")"
