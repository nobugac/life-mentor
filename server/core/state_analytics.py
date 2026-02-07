from __future__ import annotations

import datetime as dt
from typing import Any, Dict, Iterable, List, Optional

from integrations.config import get_config

from . import state_recorder


def _avg(values: Iterable[Optional[float]]) -> Optional[float]:
    items = [v for v in values if v is not None]
    if not items:
        return None
    return sum(items) / len(items)


def _extract_metrics(state: Dict[str, Any]) -> Dict[str, Optional[float]]:
    normalized = state.get("normalized") or {}
    sleep = normalized.get("sleep") or {}
    phone = normalized.get("phone_usage") or {}
    return {
        "sleep_minutes": sleep.get("total_minutes"),
        "stress_level": normalized.get("stress_level"),
        "screen_minutes": phone.get("screen_time_minutes"),
        "hrv_ms": normalized.get("hrv_ms"),
    }


def _parse_windows(value: Any, default: Optional[List[int]] = None) -> List[int]:
    if default is None:
        default = [7, 30]
    if value is None:
        return default
    if isinstance(value, list):
        return [int(v) for v in value if str(v).strip().isdigit()]
    if isinstance(value, (int, float)):
        return [int(value)]
    if isinstance(value, str):
        items = []
        for part in value.split(","):
            part = part.strip()
            if part.isdigit():
                items.append(int(part))
        return items or default
    return default


def get_trend_windows() -> List[int]:
    cfg = get_config()
    return _parse_windows(cfg.get("advice_trend_windows_days"))


def _collect_states(
    end_date: dt.date, window_days: int
) -> List[Dict[str, Any]]:
    states = []
    for offset in range(window_days):
        date = end_date - dt.timedelta(days=offset)
        state = state_recorder.load_daily_state(date)
        if state:
            states.append(state)
    return states


def summarize_state_trends(end_date: dt.date, window_days: int) -> Dict[str, Any]:
    current_states = _collect_states(end_date, window_days)
    prev_states = _collect_states(end_date - dt.timedelta(days=window_days), window_days)

    current_metrics = [_extract_metrics(s) for s in current_states]
    prev_metrics = [_extract_metrics(s) for s in prev_states]

    def metric_avg(items: List[Dict[str, Optional[float]]], key: str) -> Optional[float]:
        return _avg([m.get(key) for m in items])

    summary = {
        "window_days": window_days,
        "count": len(current_states),
        "sleep_minutes_avg": metric_avg(current_metrics, "sleep_minutes"),
        "stress_level_avg": metric_avg(current_metrics, "stress_level"),
        "screen_minutes_avg": metric_avg(current_metrics, "screen_minutes"),
        "hrv_ms_avg": metric_avg(current_metrics, "hrv_ms"),
    }

    def delta(metric: str) -> Optional[float]:
        cur = metric_avg(current_metrics, metric)
        prev = metric_avg(prev_metrics, metric)
        if cur is None or prev is None:
            return None
        return cur - prev

    summary.update(
        {
            "sleep_minutes_delta": delta("sleep_minutes"),
            "stress_level_delta": delta("stress_level"),
            "screen_minutes_delta": delta("screen_minutes"),
            "hrv_ms_delta": delta("hrv_ms"),
        }
    )
    return summary


def summarize_multi_windows(end_date: dt.date, windows: Optional[List[int]] = None) -> List[Dict[str, Any]]:
    window_list = windows or get_trend_windows()
    return [summarize_state_trends(end_date, w) for w in window_list]
