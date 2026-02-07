#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATE="${1:-$(date +%F)}"

if [[ -f "${ROOT_DIR}/scripts/env.sh" ]]; then
  # shellcheck source=/dev/null
  source "${ROOT_DIR}/scripts/env.sh"
fi

python3 - <<PY
import datetime as dt
from core import state_recorder
import manage_day

date = dt.date.fromisoformat("${DATE}")
vision_result = {
    "phone_usage": {
        "screen_time": {"total": "4h 10m", "total_minutes": 250},
        "app_usage": [
            {"app": "微信", "duration": "1h 30m", "minutes": 90},
            {"app": "浏览器", "duration": "0h 45m", "minutes": 45},
        ],
        "unlock": {"count": 120},
    },
    "watch_health": {
        "sleep": {
            "total": "5h 30m",
            "total_minutes": 330,
            "score": 70,
            "stages": {
                "deep": {"duration": "1h 0m", "minutes": 60},
                "rem": {"duration": "1h 10m", "minutes": 70},
            },
        },
        "hrv": {"value_ms": 28},
        "heart_rate": {"resting_bpm": 55},
        "spo2": {"value_percent": 98},
        "recovery": {"stress_level": 70},
    },
}

state = state_recorder.build_daily_state(date, vision_result=vision_result)
existing = state_recorder.load_daily_state(date)
merged = state_recorder.merge_daily_state(existing, state)
state_path = state_recorder.save_daily_state(merged)
note_path = manage_day.ensure_daily_file(date)
manage_day.update_device_data(note_path, merged.get("normalized") or {})

print(f"State saved: {state_path}")
print(f"Daily note updated: {note_path}")
PY
