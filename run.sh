#!/usr/bin/env bash
# Runner: venv + optional BWS injection of XAI_API_KEY / CURSOR_API_KEY.
# Usage:
#   ./run.sh smoke_test.py
#   ./run.sh read_books.py book.pdf
#   ./run.sh run_all_books.py
set -euo pipefail
cd "$(dirname "$0")"

if [[ -x "$PWD/.venv/bin/python3" ]]; then
  PYTHON="$PWD/.venv/bin/python3"
else
  PYTHON="python3"
fi
export PYTHONPATH="$PWD/.venv/lib/python3.10/site-packages${PYTHONPATH:+:$PYTHONPATH}"

if [[ -z "${BWS_ACCESS_TOKEN:-}" ]]; then
  for f in "${HERMES_ENV_FILE:-}" /var/lib/happy/.hermes/.env "${HOME}/.hermes/.env"; do
    if [[ -n "${f}" && -f "${f}" ]]; then
      set -a
      # shellcheck disable=SC1090
      source "${f}"
      set +a
      break
    fi
  done
fi

BWS_BIN=""
for c in "$(command -v bws 2>/dev/null || true)" \
         /opt/hermes-cli/.hermes/bin/bws \
         /opt/hermes-cli-prod/.hermes/bin/bws; do
  if [[ -n "${c}" && -x "${c}" ]]; then
    BWS_BIN="${c}"
    break
  fi
done

if [[ -n "${BWS_BIN}" && -n "${BWS_ACCESS_TOKEN:-}" ]]; then
  exec "${BWS_BIN}" run -- "${PYTHON}" "$@"
fi

exec "${PYTHON}" "$@"
