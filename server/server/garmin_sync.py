#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from integrations.config import get_config

try:
    from garminconnect import (
        Garmin,
        GarminConnectAuthenticationError,
        GarminConnectConnectionError,
        GarminConnectTooManyRequestsError,
    )
except ImportError as exc:
    raise SystemExit(
        "Missing dependency: garminconnect. Install with: pip install garminconnect"
    ) from exc


def resolve_date(date_arg: str | None) -> datetime.date:
    if date_arg:
        return datetime.fromisoformat(date_arg).date()
    return (datetime.now().astimezone() - timedelta(days=1)).date()


def login(client: Garmin) -> None:
    try:
        client.login()
    except GarminConnectAuthenticationError:
        mfa_code = os.environ.get("GARMIN_MFA_CODE")
        if not mfa_code:
            raise
        try:
            client.login(mfa_code)
        except TypeError as exc:
            raise GarminConnectAuthenticationError(
                "MFA provided but garminconnect login() signature is incompatible"
            ) from exc


def fetch_metric(
    client: Garmin,
    methods: list[str],
    date_str: str,
    date_obj: datetime.date,
) -> tuple[object | None, str | None]:
    last_type_error: str | None = None
    for method_name in methods:
        method = getattr(client, method_name, None)
        if not callable(method):
            continue
        for args in ((date_str,), (date_obj,)):
            try:
                return method(*args), None
            except TypeError as exc:
                last_type_error = f"{method_name} TypeError: {exc}"
                continue
            except Exception as exc:  # noqa: BLE001
                return None, f"{method_name}: {exc.__class__.__name__}: {exc}"
    return None, last_type_error or "no compatible method found"


def _data_root() -> Path:
    cfg = get_config()
    root = cfg.get("garmin_data_root")
    if root:
        return Path(str(root)).expanduser()
    data_root = cfg.get("data_root")
    if data_root:
        return Path(str(data_root)).expanduser() / "garmin"
    return Path(__file__).resolve().parents[1] / "data" / "garmin"


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch Garmin data and save JSON locally.")
    parser.add_argument("--date", help="Target date (YYYY-MM-DD). Defaults to yesterday.")
    parser.add_argument(
        "--is-cn",
        action="store_true",
        default=os.environ.get("GARMIN_IS_CN") == "1",
        help="Use Garmin China endpoints (set GARMIN_IS_CN=1).",
    )
    parser.add_argument(
        "--save-state",
        action="store_true",
        help="Normalize and save data/state JSON.",
    )
    parser.add_argument(
        "--update-note",
        action="store_true",
        help="Update the daily note device data after saving state.",
    )
    args = parser.parse_args()

    email = os.environ.get("GARMIN_EMAIL")
    password = os.environ.get("GARMIN_PASSWORD")
    if not email or not password:
        print("Set GARMIN_EMAIL and GARMIN_PASSWORD in the environment.", file=sys.stderr)
        return 1

    tokenstore = os.environ.get("GARMIN_TOKENSTORE")
    try:
        if tokenstore:
            client = Garmin(email, password, is_cn=args.is_cn, tokenstore=tokenstore)
        else:
            client = Garmin(email, password, is_cn=args.is_cn)
    except TypeError:
        client = Garmin(email, password, is_cn=args.is_cn)

    try:
        login(client)
    except (
        GarminConnectAuthenticationError,
        GarminConnectConnectionError,
        GarminConnectTooManyRequestsError,
    ) as exc:
        print(f"Login failed: {exc}", file=sys.stderr)
        return 1

    target_date = resolve_date(args.date)
    date_str = target_date.isoformat()

    metrics = {
        "sleep": ["get_sleep_data", "get_sleep_data_by_date"],
        "hrv": ["get_hrv_data", "get_hrv_data_by_date"],
        "heart_rate": ["get_heart_rates", "get_heart_rates_v2", "get_heart_rate"],
        "resting_heart_rate": ["get_rhr_day", "get_resting_heart_rate"],
        "steps": ["get_steps_data", "get_steps_data_by_date", "get_steps"],
        "daily_summary": ["get_daily_summary", "get_user_summary"],
    }

    utc_now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "source": "garmin_connect",
        "date": date_str,
        "generated_at": utc_now.isoformat().replace("+00:00", "Z"),
        "data": {},
        "errors": {},
    }

    for name, methods in metrics.items():
        value, error = fetch_metric(client, methods, date_str, target_date)
        if value is not None:
            payload["data"][name] = value
        if error:
            payload["errors"][name] = error

    out_dir = _data_root() / target_date.strftime("%Y%m%d")
    out_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"garmin_{date_str}_{utc_now.strftime('%H%M%S')}.json"
    file_path = out_dir / file_name
    file_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")

    print(f"Saved: {file_path}")

    if args.save_state or args.update_note:
        from core import state_recorder
        import manage_day

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
    raise SystemExit(main())
