from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List, Optional


DONE_STATUSES = {"done", "completed", "finish", "finished"}


def _get_cfg_int(name: str, default: int) -> int:
    try:
        from integrations.config import get_config

        cfg = get_config()
        value = cfg.get(name)
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def _parse_date(date_str: Optional[str]) -> Optional[dt.date]:
    if not date_str:
        return None
    try:
        return dt.date.fromisoformat(date_str)
    except Exception:
        return None


def _project_sort_key(project: Dict[str, Any]) -> tuple:
    deadline = _parse_date(project.get("deadline"))
    return (deadline or dt.date.max, project.get("name", ""))


def generate_daily_actions(graph: Dict[str, Any], limit: int = 3) -> List[str]:
    suggestions: List[str] = []
    projects = graph.get("projects") or []
    active_projects = [
        p for p in projects if str(p.get("status", "")).lower() not in DONE_STATUSES
    ]
    for project in sorted(active_projects, key=_project_sort_key):
        title = project.get("name")
        if not title:
            continue
        target = project.get("target")
        label = f"推进项目：{title}"
        if target:
            label += f"（{target}）"
        suggestions.append(label)
        if len(suggestions) >= limit:
            return suggestions

    goals = graph.get("goals") or []
    for goal in goals:
        title = goal.get("name")
        if not title:
            continue
        label = f"推进目标：{title}"
        suggestions.append(label)
        if len(suggestions) >= limit:
            return suggestions

    if not suggestions:
        suggestions.append("写下今天最重要的 3 件事")
    return suggestions


def _add_unique(suggestions: List[str], text: str) -> None:
    if text not in suggestions:
        suggestions.append(text)


def generate_daily_advice(
    state: Optional[Dict[str, Any]] = None,
    recent_state: Optional[str] = None,
    limit: int = 2,
    trends: Optional[List[Dict[str, Any]]] = None,
) -> List[str]:
    suggestions: List[str] = []
    sleep_low = _get_cfg_int("advice_sleep_low_minutes", 360)
    sleep_medium = _get_cfg_int("advice_sleep_medium_minutes", 420)
    stress_high = _get_cfg_int("advice_stress_high", 60)
    screen_high = _get_cfg_int("advice_screen_high_minutes", 240)
    hrv_low = _get_cfg_int("advice_hrv_low_ms", 30)

    normalized = (state or {}).get("normalized") or {}
    sleep = normalized.get("sleep") or {}
    phone = normalized.get("phone_usage") or {}

    sleep_minutes = sleep.get("total_minutes")
    stress_level = normalized.get("stress_level")
    screen_minutes = phone.get("screen_time_minutes")
    hrv_ms = normalized.get("hrv_ms")

    if sleep_minutes is not None:
        if sleep_minutes < sleep_low:
            _add_unique(suggestions, "今天优先恢复，降低任务强度并早点休息")
        elif sleep_minutes < sleep_medium:
            _add_unique(suggestions, "安排低强度任务，留出休息间隙")

    if stress_level is not None and stress_level >= stress_high:
        _add_unique(suggestions, "安排 5 分钟安静呼吸，降低压力")

    if screen_minutes is not None and screen_minutes >= screen_high:
        _add_unique(suggestions, "减少屏幕时间，给眼睛和注意力放松")

    if hrv_ms is not None and hrv_ms < hrv_low:
        _add_unique(suggestions, "今天多做恢复型活动，避免高强度刺激")

    if trends:
        for trend in trends:
            if trend.get("count", 0) == 0:
                continue
            sleep_avg = trend.get("sleep_minutes_avg")
            sleep_delta = trend.get("sleep_minutes_delta")
            if sleep_avg is not None and sleep_avg < sleep_medium:
                _add_unique(suggestions, f"近{trend['window_days']}天平均睡眠偏低，注意恢复")
            if sleep_delta is not None and sleep_delta < -30:
                _add_unique(suggestions, f"近{trend['window_days']}天睡眠下降，尝试早点休息")

            screen_avg = trend.get("screen_minutes_avg")
            screen_delta = trend.get("screen_minutes_delta")
            if screen_avg is not None and screen_avg > screen_high:
                _add_unique(suggestions, f"近{trend['window_days']}天屏幕时间偏高，减少刷屏")
            if screen_delta is not None and screen_delta > 30:
                _add_unique(suggestions, f"近{trend['window_days']}天屏幕时间上升，设定上限")

            stress_avg = trend.get("stress_level_avg")
            if stress_avg is not None and stress_avg >= stress_high:
                _add_unique(suggestions, f"近{trend['window_days']}天压力偏高，安排放松时段")

            hrv_avg = trend.get("hrv_ms_avg")
            if hrv_avg is not None and hrv_avg < hrv_low:
                _add_unique(suggestions, f"近{trend['window_days']}天 HRV 偏低，避免高强度")

    text = (recent_state or "").strip()
    if text:
        if any(word in text for word in ["累", "疲", "困", "倦"]):
            _add_unique(suggestions, "安排一次轻度恢复：散步/拉伸/热水澡")
        if any(word in text for word in ["焦虑", "压力", "烦", "紧张"]):
            _add_unique(suggestions, "给自己 5 分钟安静呼吸，降低压力")

    if not suggestions:
        suggestions.append("多笑笑，给自己一点轻松感")
    return suggestions[:limit]
