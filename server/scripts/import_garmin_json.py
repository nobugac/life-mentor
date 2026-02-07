#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import manage_day
from core import state_recorder


def _parse_iso_date(value: str | None) -> dt.date | None:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def _infer_date(payload: dict, override: str | None) -> dt.date:
    if override:
        return dt.date.fromisoformat(override)
    date_str = payload.get("date")
    if not date_str:
        date_str = ((payload.get("data") or {}).get("sleep") or {}).get("dailySleepDTO", {}).get("calendarDate")
    return _parse_iso_date(date_str) or dt.date.today()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import a Garmin JSON file into state.")
    parser.add_argument("--file", type=Path, required=True, help="Path to garmin_*.json")
    parser.add_argument("--date", type=str, help="Override date (YYYY-MM-DD)")
    parser.add_argument("--update-note", action="store_true", help="Update daily note device data")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    payload = json.loads(args.file.read_text(encoding="utf-8"))
    target_date = _infer_date(payload, args.date)

    state = state_recorder.build_daily_state_from_garmin(target_date, payload)
    existing = state_recorder.load_daily_state(target_date)
    merged = state_recorder.merge_daily_state(existing, state)
    state_path = state_recorder.save_daily_state(merged)
    print(f"State saved: {state_path}")

    if args.update_note:
        daily_path = manage_day.ensure_daily_file(target_date)
        manage_day.update_device_data(daily_path, merged.get("normalized") or {})
        print(f"Note updated: {daily_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
