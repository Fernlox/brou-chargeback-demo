#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="${ROOT_DIR}/frontend"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
DEFAULT_BACKEND_URL="http://localhost:${BACKEND_PORT}"
export NEXT_PUBLIC_BACKEND_URL="${NEXT_PUBLIC_BACKEND_URL:-${DEFAULT_BACKEND_URL}}"

cd "${FRONTEND_DIR}"
exec npm run dev -- --port "${FRONTEND_PORT}"
