#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import manage_day
from core import goal_manager


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preview weekly plan grouping.")
    parser.add_argument("--date", type=str, help="Week date (YYYY-MM-DD), default today")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("debug/weekly/week_preview.md"),
        help="Output markdown path",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    date = dt.date.fromisoformat(args.date) if args.date else dt.date.today()
    graph = goal_manager.build_goal_graph()
    goal_manager.save_goal_graph(graph)
    plan = manage_day.build_weekly_plan(graph)
    tasks_body = manage_day.render_weekly_tasks(plan).rstrip()
    iso = date.isocalendar()
    week_id = f"{iso[0]}-W{iso[1]:02d}"

    header = (
        "---\n"
        "journal: week\n"
        f"journal-date: {date.isoformat()}\n"
        f"week: {week_id}\n"
        "---\n\n"
        "# 本周任务\n"
    )
    content = header
    if tasks_body:
        content += tasks_body + "\n"
    output = args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    print(f"Preview saved: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
