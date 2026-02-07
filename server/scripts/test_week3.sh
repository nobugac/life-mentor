#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATE="${1:-$(date +%F)}"
NOTE_PATH="/Users/sean/workspace/life/note/diary/2026/day/${DATE}.md"

if [[ -f "${ROOT_DIR}/scripts/env.sh" ]]; then
  # shellcheck source=/dev/null
  source "${ROOT_DIR}/scripts/env.sh"
fi

python3 "${ROOT_DIR}/manage_day.py" \
  --date "${DATE}" \
  --evening \
  --journal "今天推进了 life-mentor开发一期，学习了新知识。虽然有点累，但总体还算顺利。"

echo "Frontmatter fields:"
if [[ -f "${NOTE_PATH}" ]]; then
  awk '
    BEGIN {in_block=0}
    /^---$/ {if (in_block==0) {in_block=1; next} else {exit}}
    in_block {print}
  ' "${NOTE_PATH}" | rg -n "^(mood|topics|linked_projects):"
else
  echo "Note not found: ${NOTE_PATH}"
fi

echo "Preview: ## 晚间总结"
if [[ -f "${NOTE_PATH}" ]]; then
  awk '
    /^## 晚间总结/ {flag=1;next}
    /^## / {flag=0}
    flag {print}
  ' "${NOTE_PATH}"
else
  echo "Note not found: ${NOTE_PATH}"
fi
