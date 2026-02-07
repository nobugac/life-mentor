#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8010}"
RELOAD="${RELOAD:-0}"
APP_MODULE="${APP_MODULE:-server.app:app}"
CONDA_ENV="${CONDA_ENV:-life_mentor_server}"
CONDA_BIN="${CONDA_BIN:-/Users/sean/miniconda3/bin/conda}"

if [[ "${CONDA_DEFAULT_ENV:-}" != "${CONDA_ENV}" && -x "${CONDA_BIN}" ]]; then
  exec "${CONDA_BIN}" run -n "${CONDA_ENV}" bash "$0" "$@"
fi

source "${ROOT_DIR}/set_env.sh"

if [[ "${HOST}" != "127.0.0.1" && "${HOST}" != "localhost" ]]; then
  LAN_IP=""
  if command -v ipconfig >/dev/null 2>&1; then
    LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || true)"
    if [[ -z "${LAN_IP}" ]]; then
      LAN_IP="$(ipconfig getifaddr en1 2>/dev/null || true)"
    fi
  fi
  if [[ -z "${LAN_IP}" ]] && command -v ifconfig >/dev/null 2>&1; then
    LAN_IP="$(ifconfig | awk '/inet / && $2 != "127.0.0.1" {print $2; exit}')"
  fi
  if [[ -n "${LAN_IP}" ]]; then
    echo "LAN: http://${LAN_IP}:${PORT}"
  fi
fi
echo "Local: http://127.0.0.1:${PORT}"

if [[ "${RELOAD}" == "1" ]]; then
  exec python -m uvicorn "${APP_MODULE}" \
    --host "${HOST}" \
    --port "${PORT}" \
    --reload \
    --reload-include "prompts/*.txt" \
    --reload-include "config/*.yaml"
fi

exec python -m uvicorn "${APP_MODULE}" --host "${HOST}" --port "${PORT}"
