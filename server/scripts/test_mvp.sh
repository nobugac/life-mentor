#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATE="${1:-$(date +%F)}"

if [[ -f "${ROOT_DIR}/scripts/env.sh" ]]; then
  # shellcheck source=/dev/null
  source "${ROOT_DIR}/scripts/env.sh"
fi

echo "Running morning flow for ${DATE}..."
python3 "${ROOT_DIR}/manage_day.py" \
  --date "${DATE}" \
  --morning \
  --text "Tired but ok. Run 30 minutes."

echo "Running evening flow for ${DATE}..."
python3 "${ROOT_DIR}/manage_day.py" \
  --date "${DATE}" \
  --evening \
  --journal "Quick test entry for MVP flow."

echo "Done. Check daily note and backup:"
echo "  Note: /Users/sean/workspace/life/note/diary/2026/day/${DATE}.md"
echo "  Backup: ${ROOT_DIR}/.backup"
