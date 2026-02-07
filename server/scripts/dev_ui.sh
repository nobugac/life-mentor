#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"

if [[ -f "${ROOT_DIR}/scripts/env.sh" ]]; then
  # shellcheck source=/dev/null
  source "${ROOT_DIR}/scripts/env.sh"
fi

echo "Starting dev UI with auto-reload on http://localhost:${PORT}"
if [[ -n "${UI_TOKEN:-}" ]]; then
  echo "UI token enabled (UI_TOKEN)"
fi

python3 - <<PY
import http.server
import os
import subprocess
import sys
import time
from pathlib import Path

root = Path("${ROOT_DIR}")
port = int("${PORT}")

watch_dirs = [
    root / "ui_server.py",
    root / "manage_day.py",
    root / "chat_bot.py",
    root / "core",
    root / "integrations",
    root / "config",
    root / "prompts",
]

def snapshot():
    stats = []
    for path in watch_dirs:
        if path.is_file():
            stats.append((path, path.stat().st_mtime))
        elif path.is_dir():
            for p in path.rglob("*.py"):
                stats.append((p, p.stat().st_mtime))
            for p in path.rglob("*.yaml"):
                stats.append((p, p.stat().st_mtime))
            for p in path.rglob("*.md"):
                stats.append((p, p.stat().st_mtime))
            for p in path.rglob("*.txt"):
                stats.append((p, p.stat().st_mtime))
    return {str(p): m for p, m in stats}


def changed(prev, cur):
    if prev.keys() != cur.keys():
        return True
    for key, val in cur.items():
        if prev.get(key) != val:
            return True
    return False


def start_server():
    args = [sys.executable, str(root / "ui_server.py"), "--host", "${HOST}", "--port", str(port)]
    token = os.environ.get("UI_TOKEN")
    if token:
        args.extend(["--token", token])
    return subprocess.Popen(
        args,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )


proc = start_server()
prev = snapshot()
try:
    while True:
        time.sleep(0.8)
        cur = snapshot()
        if changed(prev, cur):
            print("Change detected, restarting server...")
            proc.terminate()
            proc.wait(timeout=5)
            proc = start_server()
            prev = cur
except KeyboardInterrupt:
    proc.terminate()
    proc.wait(timeout=5)
PY
