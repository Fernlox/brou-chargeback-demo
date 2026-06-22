#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "${PYTHON_BIN}" ]]; then
  if [[ -x "${BACKEND_DIR}/.venv/bin/python" ]]; then
    PYTHON_BIN="${BACKEND_DIR}/.venv/bin/python"
  else
    PYTHON_BIN="${PYTHON:-python3}"
  fi
fi

cd "${ROOT_DIR}"
exec "${PYTHON_BIN}" -m uvicorn backend.main:app --reload --host "${BACKEND_HOST}" --port "${BACKEND_PORT}"
