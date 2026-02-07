#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"

if [[ -f "${ROOT_DIR}/scripts/env.sh" ]]; then
  # shellcheck source=/dev/null
  source "${ROOT_DIR}/scripts/env.sh"
fi

TOKEN_ARGS=()
if [[ -n "${UI_TOKEN:-}" ]]; then
  echo "UI token enabled (UI_TOKEN)"
  TOKEN_ARGS=(--token "${UI_TOKEN}")
fi
echo "Starting UI on http://localhost:${PORT}"
python3 "${ROOT_DIR}/ui_server.py" --host "${HOST}" --port "${PORT}" "${TOKEN_ARGS[@]}"
