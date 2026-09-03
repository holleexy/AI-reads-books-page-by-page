#!/usr/bin/env bash
# Run pending book graphs newest-knowledge-first, with a small worker pool.
# Skips books that already have a real graph.json. Does not write Hermes.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="${PWD}"
QUEUE="${QUEUE:-${ROOT}/book_analysis/semantica/queue/pending-newest.txt}"
RUN_DIR="${ROOT}/book_analysis/semantica/queue/run-$(date +%Y%m%d-%H%M%S)"
LOG_DIR="${RUN_DIR}/logs"
mkdir -p "${LOG_DIR}"
MAX_JOBS="${MAX_JOBS:-2}"
LOAD_PAUSE="${LOAD_PAUSE:-6}"
MEM_MIN_KB="${MEM_MIN_KB:-1500000}"
LIMIT="${LIMIT:-80}"
FORCE="${FORCE:-0}"
FORCE_ARGS=()
if [[ "${FORCE}" == "1" ]]; then
  FORCE_ARGS+=(--force)
fi

if [[ ! -f "${QUEUE}" ]]; then
  echo "missing queue: ${QUEUE}" >&2
  exit 1
fi

echo "run_dir=${RUN_DIR}"
echo "max_jobs=${MAX_JOBS} load_pause=${LOAD_PAUSE} mem_min_kb=${MEM_MIN_KB} limit=${LIMIT} force=${FORCE}"
cp "${QUEUE}" "${RUN_DIR}/queue.txt"
: > "${RUN_DIR}/done.txt"
: > "${RUN_DIR}/fail.txt"
: > "${RUN_DIR}/pids.txt"

book_already_running() {
  local want="$1"
  pgrep -af 'python -m book_semantica batch --book-key ' | grep -F -- "${want}" | grep -v grep >/dev/null 2>&1
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

while IFS= read -r key || [[ -n "${key}" ]]; do
  [[ -z "${key}" ]] && continue
  if [[ "${FORCE}" != "1" ]]; then
    graph="${ROOT}/book_analysis/semantica/${key}/graph.json"
    if [[ -f "${graph}" ]] && [[ -s "${graph}" ]]; then
      if python3 -c "import json,sys; p=sys.argv[1]; d=json.load(open(p)); sys.exit(0 if d.get('entities') else 1)" "${graph}" 2>/dev/null; then
        echo "skip ${key}" | tee -a "${RUN_DIR}/done.txt"
        continue
      fi
    fi
  fi
  if book_already_running "${key}"; then
    echo "already-running ${key}" | tee -a "${RUN_DIR}/progress.txt"
    continue
  fi
  wait_for_slot
  log="${LOG_DIR}/${key}.log"
  echo "$(date -Iseconds) START ${key}" | tee -a "${RUN_DIR}/progress.txt"
  (
    set +e
    "${ROOT}/scripts/run_book_semantica.sh" batch --book-key "${key}" --limit "${LIMIT}" "${FORCE_ARGS[@]}" >"${log}" 2>&1
    rc=$?
    if [[ ${rc} -eq 0 ]]; then
      echo "$(date -Iseconds) OK ${key} rc=${rc}" >> "${RUN_DIR}/progress.txt"
      echo "${key}" >> "${RUN_DIR}/done.txt"
    else
      echo "$(date -Iseconds) FAIL ${key} rc=${rc}" >> "${RUN_DIR}/progress.txt"
      echo "${key}" >> "${RUN_DIR}/fail.txt"
    fi
    exit ${rc}
  ) &
  echo "$! ${key}" >> "${RUN_DIR}/pids.txt"
done < "${RUN_DIR}/queue.txt"

wait
echo "$(date -Iseconds) ALL_DONE" | tee -a "${RUN_DIR}/progress.txt"
echo "done=$(wc -l < "${RUN_DIR}/done.txt") fail=$(wc -l < "${RUN_DIR}/fail.txt")"
