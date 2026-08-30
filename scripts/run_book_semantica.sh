#!/usr/bin/env bash
# Run the one-book Semantica pipeline with Hermes's Semantica venv.
# Does not prepend this repo's .venv site-packages onto PYTHONPATH.
set -euo pipefail
cd "$(dirname "$0")/.."

SEMANTICA_PYTHON="${SEMANTICA_PYTHON:-/var/lib/happy/.local/share/semantica/venv/bin/python}"

if [[ ! -x "${SEMANTICA_PYTHON}" ]]; then
  echo "SEMANTICA_PYTHON is not executable: ${SEMANTICA_PYTHON}" >&2
  exit 1
fi

# Drop this repo's .venv site-packages if a parent shell exported them.
if [[ -n "${PYTHONPATH:-}" ]]; then
  filtered=""
  IFS=':' read -ra parts <<< "${PYTHONPATH}"
  for p in "${parts[@]}"; do
    case "${p}" in
      "${PWD}/.venv/"*) ;;
      *)
        if [[ -n "${filtered}" ]]; then
          filtered="${filtered}:${p}"
        else
          filtered="${p}"
        fi
        ;;
    esac
  done
  PYTHONPATH="${filtered}"
fi
export PYTHONPATH="${PWD}${PYTHONPATH:+:${PYTHONPATH}}"

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

# Resolve XAI_API_KEY the same way read_books.py does (env, then Hermes OAuth).
# Uses this repo's .venv only in a child process. Does not add .venv site-packages
# to the Semantica PYTHONPATH. Does not print the token.
if [[ -z "${XAI_API_KEY:-}" && -x "${PWD}/.venv/bin/python3" ]]; then
  _xai_resolved="$(
    env -u PYTHONPATH \
      PYTHONPATH="${PWD}" \
      "${PWD}/.venv/bin/python3" -m book_semantica.resolve_xai_key
  )" || true
  if [[ -n "${_xai_resolved}" ]]; then
    export XAI_API_KEY="${_xai_resolved}"
  fi
  unset _xai_resolved
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
  exec "${BWS_BIN}" run -- "${SEMANTICA_PYTHON}" -m book_semantica "$@"
fi

exec "${SEMANTICA_PYTHON}" -m book_semantica "$@"
