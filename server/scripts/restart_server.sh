#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PORT:-8010}"
CHAT_PORT="${CHAT_PORT:-8765}"
CHAT_DIR="${ROOT_DIR}/../demo_vault/LifeMentor_Extra/Web"

echo "Stopping existing server on port ${PORT}..."
pkill -f "uvicorn.*:${PORT}" 2>/dev/null || true

echo "Stopping existing chat server on port ${CHAT_PORT}..."
pkill -f "http.server ${CHAT_PORT}" 2>/dev/null || true
sleep 1

# Start chat static server (background)
if [[ -d "${CHAT_DIR}" ]]; then
  echo "Starting chat server on http://127.0.0.1:${CHAT_PORT}..."
  cd "${CHAT_DIR}" && python3 -m http.server "${CHAT_PORT}" &>/dev/null &
  cd "${ROOT_DIR}"
fi

# Start main server
echo "Starting main server..."
exec "${ROOT_DIR}/scripts/start_server.sh" "$@"
