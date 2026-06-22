#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

BACKEND_PORT="${BACKEND_PORT:-8000}"
export BACKEND_PORT
export NEXT_PUBLIC_BACKEND_URL="${NEXT_PUBLIC_BACKEND_URL:-http://localhost:${BACKEND_PORT}}"

backend_pid=""
frontend_pid=""

cleanup() {
  if [[ -n "${frontend_pid}" ]] && kill -0 "${frontend_pid}" 2>/dev/null; then
    kill "${frontend_pid}" 2>/dev/null || true
  fi
  if [[ -n "${backend_pid}" ]] && kill -0 "${backend_pid}" 2>/dev/null; then
    kill "${backend_pid}" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

"${ROOT_DIR}/scripts/run_backend.sh" &
backend_pid=$!

sleep 2
"${ROOT_DIR}/scripts/run_frontend.sh" &
frontend_pid=$!

# macOS ships Bash 3.2, which does not support `wait -n`.
while kill -0 "${backend_pid}" 2>/dev/null && kill -0 "${frontend_pid}" 2>/dev/null; do
  sleep 1
done

backend_died=0
frontend_died=0
if ! kill -0 "${backend_pid}" 2>/dev/null; then
  backend_died=1
fi
if ! kill -0 "${frontend_pid}" 2>/dev/null; then
  frontend_died=1
fi

if [[ "${backend_died}" -eq 0 ]] && kill -0 "${backend_pid}" 2>/dev/null; then
  kill "${backend_pid}" 2>/dev/null || true
fi
if [[ "${frontend_died}" -eq 0 ]] && kill -0 "${frontend_pid}" 2>/dev/null; then
  kill "${frontend_pid}" 2>/dev/null || true
fi

set +e
wait "${backend_pid}"
backend_status=$?
wait "${frontend_pid}"
frontend_status=$?
set -e

if [[ "${backend_died}" -eq 1 ]]; then
  exit "${backend_status}"
fi
if [[ "${frontend_died}" -eq 1 ]]; then
  exit "${frontend_status}"
fi

exit 1
