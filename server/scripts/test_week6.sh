#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATE="${1:-$(date +%F)}"
NOTE_PATH="/Users/sean/workspace/life/note/diary/2026/day/${DATE}.md"
TOMORROW="$(python3 - <<'PY' "${DATE}"
import datetime as dt
import sys
date = dt.date.fromisoformat(sys.argv[1])
print((date + dt.timedelta(days=1)).isoformat())
PY
)"
TOMORROW_NOTE_PATH="/Users/sean/workspace/life/note/diary/2026/day/${TOMORROW}.md"
WEEK_NOTE_PATH="$(python3 - <<'PY' "${TOMORROW}"
import datetime as dt
import sys
from pathlib import Path
ROOT_DIR = Path.cwd()
sys.path.insert(0, str(ROOT_DIR))
from integrations.config import get_config
cfg = get_config()
week_root = Path(str(cfg.get("diary_week_root", ""))).expanduser()
date = dt.date.fromisoformat(sys.argv[1])
iso = date.isocalendar()
week_id = f\"{iso.year}-W{iso.week:02d}\"
path = week_root / f\"{week_id}.md\"
print(path)
PY
)"

if [[ -f "${ROOT_DIR}/scripts/env.sh" ]]; then
  # shellcheck source=/dev/null
  source "${ROOT_DIR}/scripts/env.sh"
fi

python3 "${ROOT_DIR}/manage_day.py" \
  --date "${DATE}" \
  --evening \
  --journal "今天完成了晚间增强测试，准备输出建议与明日任务。"

echo "Preview: ## 晚间建议"
if [[ -f "${NOTE_PATH}" ]]; then
  awk '
    /^## 晚间建议/ {flag=1;next}
    /^## / {flag=0}
    flag {print}
  ' "${NOTE_PATH}"
else
  echo "Note not found: ${NOTE_PATH}"
fi

echo "Preview: 次日 ## 今日任务"
if [[ -f "${TOMORROW_NOTE_PATH}" ]]; then
  awk '
    /^## 今日任务/ {flag=1;next}
    /^## / {flag=0}
    flag {print}
  ' "${TOMORROW_NOTE_PATH}"
else
  echo "Note not found: ${TOMORROW_NOTE_PATH}"
fi

echo "Preview: 周记 # 本周任务 (仅周日生成)"
if [[ -f "${WEEK_NOTE_PATH}" ]]; then
  awk '
    /^# 本周任务/ {flag=1;next}
    /^# / {flag=0}
    flag {print}
  ' "${WEEK_NOTE_PATH}"
else
  echo "Note not found: ${WEEK_NOTE_PATH}"
fi
