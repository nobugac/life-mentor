#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -f "${ROOT_DIR}/set_env.sh" ]]; then
  # shellcheck source=/dev/null
  source "${ROOT_DIR}/set_env.sh"
else
  export GEMINI_API_KEY="${GEMINI_API_KEY:-}"
  export ARK_API_KEY="${ARK_API_KEY:-}"
  export OPENAI_API_KEY="${OPENAI_API_KEY:-}"
  export OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}"
fi
