#!/usr/bin/env python3
"""Auto-restart UI server on file changes (no extra deps).

Usage: python dev_ui.py --port 8000
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Dev runner with auto-reload.")
    parser.add_argument("--port", type=str, default="8000")
    return parser.parse_args(argv)


def collect_mtimes(paths):
    mtimes = {}
    for p in paths:
        try:
            mtimes[p] = p.stat().st_mtime
        except FileNotFoundError:
            mtimes[p] = 0
    return mtimes


def changed(prev, curr):
    for p, m in curr.items():
        if prev.get(p, 0) != m:
            return True
    return False


def main(argv=None) -> int:
    args = parse_args(argv or [])
    root = Path(__file__).resolve().parent
    watch_files = [
        root / "ui_server.py",
        root / "chat_bot.py",
        root / "manage_day.py",
        root / "set_env.sh",
    ]

    cmd = [sys.executable, str(root / "ui_server.py"), "--port", args.port]
    proc = subprocess.Popen(cmd, cwd=str(root))
    mtimes = collect_mtimes(watch_files)

    try:
        while True:
            time.sleep(1)
            new_mtimes = collect_mtimes(watch_files)
            if changed(mtimes, new_mtimes):
                mtimes = new_mtimes
                try:
                    proc.send_signal(signal.SIGTERM)
                except Exception:
                    pass
                proc.wait(timeout=5)
                proc = subprocess.Popen(cmd, cwd=str(root))
    except KeyboardInterrupt:
        pass
    finally:
        try:
            proc.send_signal(signal.SIGTERM)
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
