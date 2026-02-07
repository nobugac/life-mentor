#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATE="${1:-$(date +%F)}"
NOTE_PATH="/Users/sean/workspace/life/note/diary/2026/day/${DATE}.md"

if [[ -f "${ROOT_DIR}/scripts/env.sh" ]]; then
  # shellcheck source=/dev/null
  source "${ROOT_DIR}/scripts/env.sh"
fi

echo "Running morning flow for ${DATE}..."
python3 "${ROOT_DIR}/manage_day.py" \
  --date "${DATE}" \
  --morning \
  --text "Test state. Walk 20 minutes."

echo "Preview: ## 今日任务"
if [[ -f "${NOTE_PATH}" ]]; then
  awk '
    /^## 今日任务/ {flag=1;next}
    /^## / {flag=0}
    flag {print}
  ' "${NOTE_PATH}"
else
  echo "Note not found: ${NOTE_PATH}"
fi

echo "Preview: ## 今日建议"
if [[ -f "${NOTE_PATH}" ]]; then
  awk '
    /^## 今日建议/ {flag=1;next}
    /^## / {flag=0}
    flag {print}
  ' "${NOTE_PATH}"
else
  echo "Note not found: ${NOTE_PATH}"
fi

echo "Cache saved: ${ROOT_DIR}/data/cache/goal_graph.json"
