#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATE="${1:-$(date +%F)}"
STATE_PATH="${ROOT_DIR}/data/state/${DATE}.json"
NOTE_PATH="/Users/sean/workspace/life/note/diary/2026/day/${DATE}.md"

if [[ -f "${ROOT_DIR}/scripts/env.sh" ]]; then
  # shellcheck source=/dev/null
  source "${ROOT_DIR}/scripts/env.sh"
fi

mkdir -p "$(dirname "${STATE_PATH}")"

cat > "${STATE_PATH}" <<EOF
{
  "date": "${DATE}",
  "normalized": {
    "sleep": {
      "total_minutes": 330,
      "deep_minutes": 60,
      "rem_minutes": 70
    },
    "phone_usage": {
      "screen_time_minutes": 300,
      "unlock_count": 120
    },
    "hrv_ms": 28,
    "resting_bpm": 55,
    "spo2_percent": 98,
    "stress_level": 70
  }
}
EOF

echo "Saved mock state: ${STATE_PATH}"

if [[ "${GENERATE_TREND:-0}" == "1" ]]; then
  for offset in {1..6}; do
    d="$(DATE="${DATE}" OFFSET="${offset}" python3 - <<'PY'
import datetime as dt
import os
date = os.environ["DATE"]
offset = int(os.environ["OFFSET"])
target = dt.date.fromisoformat(date) - dt.timedelta(days=offset)
print(target.isoformat())
PY
)"
    path="${ROOT_DIR}/data/state/${d}.json"
    if [[ -f "${path}" ]]; then
      continue
    fi
    cat > "${path}" <<EOF
{
  "date": "${d}",
  "normalized": {
    "sleep": { "total_minutes": 380 },
    "phone_usage": { "screen_time_minutes": $((200 + offset * 20)) },
    "hrv_ms": 35,
    "stress_level": 55
  }
}
EOF
  done
  echo "Generated mock trend data for previous 6 days (if missing)."
fi

python3 "${ROOT_DIR}/manage_day.py" \
  --date "${DATE}" \
  --morning \
  --text "有点累"

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
