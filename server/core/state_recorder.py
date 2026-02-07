from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any, Dict, Optional

from integrations.config import get_config


def _to_minutes(value: Optional[Any]) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value)
    matches = re.findall(r"(\\d+)", text)
    if not matches:
        return None
    nums = [int(n) for n in matches]
    if "小时" in text or "h" in text.lower():
        hours = nums[0]
        minutes = nums[1] if len(nums) > 1 else 0
        return hours * 60 + minutes
    if "分" in text or "min" in text.lower():
        return nums[0]
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    return nums[0]


def _seconds_to_minutes(value: Optional[Any]) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(round(float(value) / 60))
    text = str(value).strip()
    if text.isdigit():
        return int(round(int(text) / 60))
    return _to_minutes(text)


def _average(values: list[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values) / len(values)


def _parse_iso_datetime(value: Optional[str]) -> Optional[dt.datetime]:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _duration_minutes(start: Optional[dt.datetime], end: Optional[dt.datetime]) -> Optional[int]:
    if not start or not end:
        return None
    delta = end - start
    if delta.total_seconds() < 0:
        return None
    return int(round(delta.total_seconds() / 60))


def _normalize_phone_usage(phone: Dict[str, Any]) -> Dict[str, Any]:
    screen_time = phone.get("screen_time") or {}
    screen_minutes = screen_time.get("total_minutes")
    if screen_minutes is None:
        screen_minutes = _to_minutes(screen_time.get("total"))
    unlock = phone.get("unlock") or {}
    unlock_count = unlock.get("count")
    apps = []
    for entry in phone.get("app_usage") or []:
        if not isinstance(entry, dict):
            continue
        name = entry.get("app")
        minutes = entry.get("minutes")
        if minutes is None:
            minutes = _to_minutes(entry.get("duration"))
        if name or minutes is not None:
            apps.append({"name": name, "minutes": minutes})
    return {
        "screen_time_minutes": screen_minutes,
        "unlock_count": unlock_count,
        "top_apps": apps,
    }


def _normalize_sleep(sleep: Dict[str, Any]) -> Dict[str, Any]:
    total_minutes = sleep.get("total_minutes")
    if total_minutes is None:
        total_minutes = _to_minutes(sleep.get("total") or sleep.get("duration_display"))
    stages = sleep.get("stages") or {}
    def _stage_minutes(key: str) -> Optional[int]:
        stage = stages.get(key) or {}
        minutes = stage.get("minutes")
        if minutes is None:
            minutes = _to_minutes(stage.get("duration"))
        return minutes

    return {
        "total_minutes": total_minutes,
        "deep_minutes": _stage_minutes("deep"),
        "rem_minutes": _stage_minutes("rem"),
        "light_minutes": _stage_minutes("light"),
        "awake_minutes": _stage_minutes("awake"),
        "score": sleep.get("score"),
    }


def _normalize_health_sleep(health: Dict[str, Any]) -> Dict[str, Any]:
    stage_totals: Dict[str, int] = {"deep": 0, "light": 0, "rem": 0, "awake": 0}
    stage_samples = health.get("sleepStages") or []
    for sample in stage_samples:
        if not isinstance(sample, dict):
            continue
        stage_raw = str(sample.get("stage") or "").lower()
        if not stage_raw:
            continue
        if "deep" in stage_raw:
            key = "deep"
        elif "light" in stage_raw:
            key = "light"
        elif "rem" in stage_raw:
            key = "rem"
        elif "awake" in stage_raw or "out" in stage_raw:
            key = "awake"
        else:
            continue
        start = _parse_iso_datetime(sample.get("startTime"))
        end = _parse_iso_datetime(sample.get("endTime"))
        minutes = _duration_minutes(start, end)
        if minutes is not None:
            stage_totals[key] += minutes

    total_minutes = sum(stage_totals.values()) if any(stage_totals.values()) else None
    if total_minutes is None:
        session_minutes = 0
        for session in health.get("sleepSessions") or []:
            if not isinstance(session, dict):
                continue
            start = _parse_iso_datetime(session.get("startTime"))
            end = _parse_iso_datetime(session.get("endTime"))
            minutes = _duration_minutes(start, end)
            if minutes is not None:
                session_minutes += minutes
        if session_minutes:
            total_minutes = session_minutes

    return {
        "total_minutes": total_minutes,
        "deep_minutes": stage_totals["deep"] or None,
        "rem_minutes": stage_totals["rem"] or None,
        "light_minutes": stage_totals["light"] or None,
        "awake_minutes": stage_totals["awake"] or None,
        "score": None,
    }


def normalize_mobile_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    usage_total_ms = payload.get("usageTotalMs") or payload.get("usage_total_ms")
    screen_minutes = None
    if usage_total_ms is not None:
        screen_minutes = int(round(float(usage_total_ms) / 60000))
    night_usage_ms = (
        payload.get("nightUsageTotalMs")
        or payload.get("night_usage_total_ms")
        or payload.get("nightScreenMs")
    )
    night_screen_minutes = payload.get("nightScreenMinutes")
    if night_screen_minutes is None and night_usage_ms is not None:
        night_screen_minutes = int(round(float(night_usage_ms) / 60000))
    apps = []
    for entry in payload.get("usageByApp") or payload.get("usage_by_app") or []:
        if not isinstance(entry, dict):
            continue
        name = entry.get("packageName") or entry.get("name") or entry.get("app")
        total_ms = entry.get("totalTimeMs") or entry.get("total_time_ms")
        minutes = None
        if total_ms is not None:
            minutes = int(round(float(total_ms) / 60000))
        if name or minutes is not None:
            apps.append({"name": name, "minutes": minutes})

    night_apps = []
    for entry in payload.get("nightUsageByApp") or payload.get("night_usage_by_app") or []:
        if not isinstance(entry, dict):
            continue
        name = entry.get("packageName") or entry.get("name") or entry.get("app")
        total_ms = entry.get("totalTimeMs") or entry.get("total_time_ms")
        minutes = None
        if total_ms is not None:
            minutes = int(round(float(total_ms) / 60000))
        if name or minutes is not None:
            night_apps.append({"name": name, "minutes": minutes})

    normalized: Dict[str, Any] = {
        "phone_usage": {
            "screen_time_minutes": screen_minutes,
            "night_screen_minutes": night_screen_minutes,
            "unlock_count": payload.get("unlockCount"),
            "top_apps": apps,
            "night_top_apps": night_apps,
        }
    }

    health = payload.get("health") or {}
    if isinstance(health, dict):
        hrv_samples = [s.get("rmssdMs") for s in health.get("hrvRmssd") or [] if isinstance(s, dict)]
        hrv_values = [float(v) for v in hrv_samples if v is not None]
        hrv_ms = _average(hrv_values)
        resting_samples = [s.get("bpm") for s in health.get("restingHeartRate") or [] if isinstance(s, dict)]
        resting_values = [float(v) for v in resting_samples if v is not None]
        resting_bpm = _average(resting_values)
        if hrv_ms is not None:
            normalized["hrv_ms"] = int(round(hrv_ms))
        if resting_bpm is not None:
            normalized["resting_bpm"] = int(round(resting_bpm))
    return normalized


def _normalize_garmin_sleep(sleep: Dict[str, Any]) -> Dict[str, Any]:
    daily = sleep.get("dailySleepDTO") or {}
    scores = daily.get("sleepScores") or {}
    overall = scores.get("overall") or {}
    score = overall.get("value") or daily.get("sleepScore")
    return {
        "total_minutes": _seconds_to_minutes(daily.get("sleepTimeSeconds")),
        "deep_minutes": _seconds_to_minutes(daily.get("deepSleepSeconds")),
        "rem_minutes": _seconds_to_minutes(daily.get("remSleepSeconds")),
        "light_minutes": _seconds_to_minutes(daily.get("lightSleepSeconds")),
        "awake_minutes": _seconds_to_minutes(daily.get("awakeSleepSeconds")),
        "score": score,
    }


def normalize_garmin_result(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        data = payload or {}
    sleep = data.get("sleep") or {}
    daily = sleep.get("dailySleepDTO") or {}
    normalized_sleep = _normalize_garmin_sleep(sleep)

    hrv = data.get("hrv") or {}
    hrv_summary = hrv.get("hrvSummary") or {}
    hrv_ms = hrv_summary.get("lastNightAvg")
    if hrv_ms is None:
        hrv_ms = sleep.get("avgOvernightHrv")

    heart_rate = data.get("heart_rate") or {}
    resting_bpm = heart_rate.get("restingHeartRate")
    if resting_bpm is None:
        rhr = data.get("resting_heart_rate") or {}
        metrics_map = (rhr.get("allMetrics") or {}).get("metricsMap") or {}
        entries = metrics_map.get("WELLNESS_RESTING_HEART_RATE") or []
        if entries and isinstance(entries, list):
            last_entry = entries[-1]
            if isinstance(last_entry, dict):
                resting_bpm = last_entry.get("value")

    summary = data.get("daily_summary") or {}
    stress_level = summary.get("averageStressLevel")
    if stress_level is None:
        stress_level = daily.get("avgSleepStress")

    spo2_percent = daily.get("averageSpO2Value")

    return {
        "sleep": normalized_sleep,
        "hrv_ms": hrv_ms,
        "resting_bpm": resting_bpm,
        "spo2_percent": spo2_percent,
        "stress_level": stress_level,
    }


def normalize_vision_result(result: Dict[str, Any]) -> Dict[str, Any]:
    phone = result.get("phone_usage") or {}
    watch = result.get("watch_health") or {}
    sleep = watch.get("sleep") or {}
    normalized_sleep = _normalize_sleep(sleep)
    return {
        "phone_usage": _normalize_phone_usage(phone),
        "sleep": {
            "total_minutes": normalized_sleep.get("total_minutes"),
            "deep_minutes": normalized_sleep.get("deep_minutes"),
            "rem_minutes": normalized_sleep.get("rem_minutes"),
            "light_minutes": normalized_sleep.get("light_minutes"),
            "awake_minutes": normalized_sleep.get("awake_minutes"),
            "score": normalized_sleep.get("score"),
        },
        "hrv_ms": (watch.get("hrv") or {}).get("value_ms"),
        "resting_bpm": (watch.get("heart_rate") or {}).get("resting_bpm"),
        "spo2_percent": (watch.get("spo2") or {}).get("value_percent"),
        "stress_level": (watch.get("recovery") or {}).get("stress_level"),
    }


def _derive_metrics(normalized: Dict[str, Any]) -> Dict[str, Any]:
    sleep = normalized.get("sleep") or {}
    total = sleep.get("total_minutes")
    awake = sleep.get("awake_minutes")
    derived: Dict[str, Any] = {}
    if total and awake is not None and total > 0:
        derived["sleep_efficiency"] = round((total - awake) / total, 4)
    return derived


def build_daily_state(
    date: dt.date,
    vision_result: Optional[Dict[str, Any]] = None,
    text_input: Optional[str] = None,
) -> Dict[str, Any]:
    normalized = normalize_vision_result(vision_result or {})
    return {
        "date": date.isoformat(),
        "raw": {
            "vision": vision_result,
            "text": text_input,
        },
        "normalized": normalized,
        "derived": _derive_metrics(normalized),
    }


def build_daily_state_from_mobile(date: dt.date, payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_mobile_payload(payload or {})
    return {
        "date": date.isoformat(),
        "raw": {
            "mobile": payload,
        },
        "normalized": normalized,
        "derived": _derive_metrics(normalized),
    }


def build_daily_state_from_garmin(date: dt.date, payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_garmin_result(payload or {})
    return {
        "date": date.isoformat(),
        "raw": {
            "garmin": payload,
        },
        "normalized": normalized,
        "derived": _derive_metrics(normalized),
    }


def merge_daily_state(existing: Optional[Dict[str, Any]], incoming: Dict[str, Any]) -> Dict[str, Any]:
    if not existing:
        return incoming
    merged: Dict[str, Any] = dict(existing)
    merged["date"] = incoming.get("date") or existing.get("date")

    raw = dict(existing.get("raw") or {})
    raw.update(incoming.get("raw") or {})
    merged["raw"] = raw

    merged_normalized = dict(existing.get("normalized") or {})
    incoming_normalized = incoming.get("normalized") or {}
    for key, value in incoming_normalized.items():
        if key in {"sleep", "phone_usage"} and isinstance(value, dict):
            merged_section = dict(merged_normalized.get(key) or {})
            for section_key, section_value in value.items():
                if section_value is not None:
                    merged_section[section_key] = section_value
            merged_normalized[key] = merged_section
        elif value is not None:
            merged_normalized[key] = value

    merged["normalized"] = merged_normalized
    merged["derived"] = _derive_metrics(merged_normalized)
    return merged


def save_daily_state(state: Dict[str, Any], state_root: Optional[Path] = None) -> Path:
    cfg = get_config()
    root = state_root or Path(str(cfg.get("state_root", ""))).expanduser()
    if not root:
        raise ValueError("state_root is not configured")
    root.mkdir(parents=True, exist_ok=True)
    date_str = state.get("date")
    if not date_str:
        raise ValueError("state.date is required")
    path = root / f"{date_str}.json"
    path.write_text(json.dumps(state, ensure_ascii=True, indent=2), encoding="utf-8")
    return path


def load_daily_state(date: dt.date, state_root: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    cfg = get_config()
    root = state_root or Path(str(cfg.get("state_root", ""))).expanduser()
    if not root:
        raise ValueError("state_root is not configured")
    path = root / f"{date.isoformat()}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_vision_result(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and data.get("result"):
        return data.get("result") or {}
    raw = data.get("raw") if isinstance(data, dict) else None
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {}
    return {}
