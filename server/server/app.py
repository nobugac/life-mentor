from __future__ import annotations

import base64
import json
import os
import traceback
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

import chat_bot
import manage_day
import ui_server
from core import record_store
from core import goal_manager
from core import llm_analyzer
from core import state_analytics
from core import state_recorder
from integrations.config import get_config


app = FastAPI()

# CORS for chat.html and Obsidian iframe access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

CFG = get_config()
REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = Path(str(CFG.get("data_root", REPO_ROOT / "data"))).expanduser()
MOBILE_ROOT = Path(str(CFG.get("mobile_data_root", DATA_ROOT / "mobile"))).expanduser()
GARMIN_ROOT = Path(str(CFG.get("garmin_data_root", DATA_ROOT / "garmin"))).expanduser()
AUTO_UPDATE_NOTE = bool(CFG.get("auto_update_daily_note", False))
SYNC_LOG_PATH = DATA_ROOT / "sync_log.jsonl"
ACTIVE_GOALS_PATH = REPO_ROOT / "config" / "active_goals.md"
SUGGESTION_ACTION_LOG = DATA_ROOT / "suggestion_actions.jsonl"
WEEKLY_FOCUS_ROOT = DATA_ROOT / "weekly_focus"
# Obsidian display data directory (synced to Android via Obsidian Sync)
OB_DISPLAY_DATA_ROOT = Path(str(CFG.get("vault_root", ""))).expanduser() / "LifeMentor_Extra" / "Data"

UI_TOKEN = None
_token_value = os.environ.get("UI_TOKEN") or os.environ.get("LIFE_MENTOR_UI_TOKEN")
if _token_value and _token_value.strip():
    UI_TOKEN = _token_value.strip()
if not UI_TOKEN:
    cfg_token = CFG.get("ui_token")
    if isinstance(cfg_token, str) and cfg_token.strip():
        UI_TOKEN = cfg_token.strip()

GOAL_TEXT: Optional[str] = None
_goal_path = os.environ.get("LIFE_MENTOR_GOAL_FILE")
if _goal_path:
    GOAL_TEXT = chat_bot.read_goal_text(Path(_goal_path))


class UploadPayload(BaseModel):
    deviceId: str
    rangeStart: str
    rangeEnd: str
    generatedAt: str
    localDate: Optional[str] = None
    nightUsageTotalMs: Optional[int] = None
    nightUsageByApp: Optional[list] = None
    usageTotalMs: int
    usageByApp: list
    health: dict


def _model_dump(payload: BaseModel) -> dict:
    if hasattr(payload, "model_dump"):
        return payload.model_dump()  # type: ignore[call-arg]
    return payload.dict()


def _parse_iso_date(value: Optional[str]) -> Optional[datetime.date]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _parse_date(value: Optional[str]) -> Optional[datetime.date]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")


def _update_note(date: datetime.date, normalized: dict, update_note: bool) -> Optional[Path]:
    if not update_note:
        return None
    daily_path = manage_day.ensure_daily_file(date)
    manage_day.update_device_data(daily_path, normalized)
    return daily_path


def _status_from_normalized(normalized: dict) -> dict[str, Optional[float]]:
    sleep = normalized.get("sleep") or {}
    phone = normalized.get("phone_usage") or {}
    total_minutes = sleep.get("total_minutes")
    sleep_hours = round(total_minutes / 60.0, 1) if total_minutes is not None else None
    screen_minutes = phone.get("screen_time_minutes")
    screen_hours = round(screen_minutes / 60.0, 1) if screen_minutes is not None else None
    night_minutes = phone.get("night_screen_minutes")
    night_hours = round(night_minutes / 60.0, 1) if night_minutes is not None else None
    score = sleep.get("score")
    return {
        "sleep_hours": sleep_hours,
        "sleep_score": score,
        "screen_time_hours": screen_hours,
        "night_screen_hours": night_hours,
    }


def _append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, ensure_ascii=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def _save_ob_display_data(name: str, data: dict) -> None:
    """Save display data to Obsidian vault for sync to Android."""
    try:
        OB_DISPLAY_DATA_ROOT.mkdir(parents=True, exist_ok=True)
        path = OB_DISPLAY_DATA_ROOT / f"{name}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass  # Don't fail the request if display data save fails


def _get_week_key(date: datetime.date) -> str:
    """Get ISO week key like '2026-W05'."""
    return date.strftime("%G-W%V")


def _load_weekly_focus(date: datetime.date) -> Optional[dict]:
    """Load the selected weekly focus for the week containing the given date."""
    week_key = _get_week_key(date)
    path = WEEKLY_FOCUS_ROOT / f"{week_key}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def _save_weekly_focus(date: datetime.date, focus: dict) -> None:
    """Save the selected weekly focus."""
    week_key = _get_week_key(date)
    WEEKLY_FOCUS_ROOT.mkdir(parents=True, exist_ok=True)
    path = WEEKLY_FOCUS_ROOT / f"{week_key}.json"
    data = {
        "week": week_key,
        "selected_at": datetime.now().isoformat(),
        "focus": focus,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    # Also save to Obsidian for sync
    _save_ob_display_data("weekly_focus", data)


def _generate_focus_options(active_goals: list, trends: dict) -> list:
    """Generate focus options based on goals and trends."""
    options = []
    focus_templates = [
        {"name": "Sleep Guard", "intent": "Sleep ≥ 7h every day", "why": "Sleep is the foundation of energy — protect it first"},
        {"name": "Screen Boundary", "intent": "Phone < 2h per day", "why": "Reduce mindless scrolling, focus on what matters"},
        {"name": "Morning Launch", "intent": "Start first task within 30 min of waking", "why": "Beat procrastination with action"},
        {"name": "Bedtime Wind-down", "intent": "No phone 1 hour before bed", "why": "Lower the barrier to falling asleep"},
        {"name": "Exercise Activation", "intent": "Exercise ≥ 3 times per week", "why": "Physical health powers everything else"},
    ]
    for i, tmpl in enumerate(focus_templates[:3]):
        options.append({
            "id": f"focus_{i}",
            "name": tmpl["name"],
            "intent": tmpl["intent"],
            "why": tmpl["why"],
        })
    return options


def _mock_morning_result() -> dict:
    """Return fallback data when LLM is unavailable."""
    return {
        "advice": ["Tonight at 11 PM, put your phone on the living room charger (just this one step)."],
        "ideas": [
            "Take a 10-minute walk after lunch",
            "Drink a glass of water at 3 PM",
            "Write 3 things you're grateful for before bed",
        ],
        "alignment_note": "Health → Sleep ≥ 7h → reduce stimulation before bed",
        "tasks": [],
    }


def _mock_evening_result() -> dict:
    """Return fallback data when LLM is unavailable."""
    return {
        "summary": "Good rhythm today — steady progress on key tasks. Some interruptions, but you held it together.",
        "mood": "good",
        "topics": ["work", "focus"],
        "reflection": "You actually held up well today: finished core work, navigated technical blocks.\n\nSuggestion: try winding down at 10:30 PM, give yourself transition time. Keep tomorrow's pace steady — don't rush to do more, stabilize what you've done.",
    }


def _mock_alignment_result() -> dict:
    """Return fallback data when LLM is unavailable."""
    return {
        "metrics": {
            "sleep_hours": 6.5,
            "sleep_score": 72,
            "screen_time_hours": 4.2,
            "night_screen_hours": 1.1,
        },
        "pattern": "Post-dinner scrolling → can't stop before bed → lower energy next day → harder to exercise/sleep early.",
        "value_board": [
            {
                "value": "Health",
                "role": "main",
                "trend": "down",
                "summary": "Slightly late nights, maintain baseline",
            },
            {
                "value": "Inner Growth",
                "role": "sub",
                "trend": "flat",
                "summary": "Learning pace is steady",
            },
            {
                "value": "Wealth",
                "role": "sub",
                "trend": "up",
                "summary": "Spending more restrained, surplus growing",
            },
        ],
        "focus": {
            "name": "Sleep Guard: move phone away from bed",
            "intent": "Health — reduce late-night phone use to protect sleep",
            "why": "Recently it's been harder to stop scrolling after dinner; bedtime phone usage is elevated.",
        },
    }


def _normalize_goal_list(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen = set()
    ignore = {"values", "goals"}
    for raw in values:
        if not raw:
            continue
        item = raw.strip()
        if not item:
            continue
        if item.startswith("- "):
            item = item[2:].strip()
        if item.startswith("* "):
            item = item[2:].strip()
        if item.startswith("#"):
            continue
        if item.lower() in ignore:
            continue
        if item in seen:
            continue
        seen.add(item)
        cleaned.append(item)
    return cleaned


def _list_goal_files(path_value: Optional[object]) -> list[str]:
    if not path_value:
        return []
    path = Path(str(path_value)).expanduser()
    if not path.exists() or not path.is_dir():
        return []
    files = [p.stem for p in path.iterdir() if p.is_file() and p.suffix.lower() == ".md"]
    return sorted(_normalize_goal_list(files))


def _load_goal_options() -> list[str]:
    values_dir = CFG.get("values_dir")
    goals_dir = CFG.get("goals_dir")
    combined = _list_goal_files(values_dir) + _list_goal_files(goals_dir)
    return _normalize_goal_list(combined)


def _load_active_goals() -> list[str]:
    if not ACTIVE_GOALS_PATH.exists():
        return []
    lines = ACTIVE_GOALS_PATH.read_text(encoding="utf-8").splitlines()
    return _normalize_goal_list(lines)


def _save_active_goals(goals: list[str]) -> None:
    cleaned = _normalize_goal_list(goals)
    body = "\n".join(f"- {item}" for item in cleaned)
    ACTIVE_GOALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    ACTIVE_GOALS_PATH.write_text(body + ("\n" if body else ""), encoding="utf-8")


def _extract_token(request: Request, payload: Optional[dict] = None) -> Optional[str]:
    header_token = request.headers.get("X-UI-Token")
    if header_token:
        return header_token.strip()
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()
    if payload and isinstance(payload, dict):
        value = payload.get("token")
        if isinstance(value, str) and value.strip():
            return value.strip()
    token_param = request.query_params.get("token")
    if token_param:
        return token_param.strip()
    return None


def _authorized(request: Request, payload: Optional[dict] = None) -> bool:
    if not UI_TOKEN:
        return True
    token = _extract_token(request, payload)
    return bool(token) and token == UI_TOKEN


def _error(status: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": message})


@app.get("/")
async def index(request: Request):
    if not _authorized(request):
        body = (
            "<html><body><h3>Unauthorized</h3>"
            "<p>Add token in URL, e.g. http://IP:8001/?token=YOUR_TOKEN</p>"
            "</body></html>"
        )
        return HTMLResponse(body, status_code=401)
    return HTMLResponse(ui_server.INDEX_HTML)


@app.post("/chat")
async def chat(payload: dict, request: Request):
    if not _authorized(request, payload):
        return _error(401, "unauthorized")
    message = payload.get("message")
    date_str = payload.get("date")
    provider = payload.get("provider") or "ark"
    model = payload.get("model") or (
        chat_bot.DEFAULT_ARK_MODEL if provider in ("ark", "doubao") else chat_bot.DEFAULT_MODEL
    )
    if not message:
        return _error(400, "missing message")
    try:
        date = datetime.fromisoformat(date_str).date() if date_str else datetime.now().date()
    except Exception:
        return _error(400, "invalid date")

    try:
        client = chat_bot.make_client(provider)
        parsed = chat_bot.classify_message(client, model, message, GOAL_TEXT)
        action = parsed.get("action", "none")
        text_input = parsed.get("text")
        journal = parsed.get("journal")
        images = parsed.get("images", []) or []
        file_path = chat_bot.apply_action(action, date, GOAL_TEXT, text_input, journal, images)

        # Log chat to diary
        reply = parsed.get("reply", "")
        try:
            daily_path = manage_day.ensure_daily_file(date)
            chat_text = f"User: {message}\nLM: {reply}"
            manage_day.append_journal_entry(daily_path, "Chat", chat_text)
        except Exception:
            pass

        return {"action": action, "file": str(file_path), "parsed": parsed}
    except Exception as exc:
        traceback.print_exc()
        return _error(500, str(exc))


@app.post("/alignment")
async def alignment(payload: dict, request: Request):
    if not _authorized(request, payload):
        return _error(401, "unauthorized")
    debug = bool(payload.get("debug"))
    skip_llm = bool(payload.get("skip_llm"))
    mock = bool(payload.get("mock"))
    timing: dict[str, int] = {}
    total_start = time.monotonic()
    date_str = payload.get("date")
    try:
        target_date = datetime.fromisoformat(date_str).date() if date_str else datetime.now().date() - timedelta(days=1)
    except Exception:
        return _error(400, "invalid date")

    load_start = time.monotonic()
    state = state_recorder.load_daily_state(target_date) or {}
    if debug:
        timing["load_state_ms"] = int((time.monotonic() - load_start) * 1000)
    normalized = state.get("normalized") or {}
    sleep = normalized.get("sleep") or {}
    if sleep.get("total_minutes") is None:
        try:
            garmin_start = time.monotonic()
            raw = ui_server._fetch_garmin_payload(target_date)
            incoming = state_recorder.build_daily_state_from_garmin(target_date, raw)
            merged = state_recorder.merge_daily_state(state, incoming)
            state_recorder.save_daily_state(merged)
            state = merged
            normalized = merged.get("normalized") or {}
            if debug:
                timing["garmin_fetch_ms"] = int((time.monotonic() - garmin_start) * 1000)
        except Exception:
            pass

    metrics = _status_from_normalized(normalized)
    goals_start = time.monotonic()
    active_goals = _load_active_goals()
    goal_options = _load_goal_options()
    if debug:
        timing["goals_ms"] = int((time.monotonic() - goals_start) * 1000)

    snapshot = None
    pattern = None
    value_board: list[dict[str, Any]] = []
    focus: dict[str, Any] | None = None
    record_texts: list[str] = []
    try:
        records = record_store.load_records(target_date)
        record_texts = record_store.summarize_records(records)
        if len(record_texts) > 2:
            record_texts = record_texts[-2:]
    except Exception:
        record_texts = []
    if mock:
        # Use mock data for demo/development
        mock_data = _mock_alignment_result()
        pattern = mock_data.get("pattern")
        value_board = mock_data.get("value_board", [])
        focus = mock_data.get("focus")
        # Use mock metrics if real metrics are empty
        if not any(v for v in metrics.values() if v is not None):
            metrics = mock_data.get("metrics", {})
    elif not skip_llm:
        try:
            graph_start = time.monotonic()
            graph = goal_manager.build_goal_graph()
            goal_manager.save_goal_graph(graph)
            if debug:
                timing["goal_graph_ms"] = int((time.monotonic() - graph_start) * 1000)
            trends_start = time.monotonic()
            trends = state_analytics.summarize_multi_windows(target_date)
            if debug:
                timing["trends_ms"] = int((time.monotonic() - trends_start) * 1000)
            llm_start = time.monotonic()
            llm_result = llm_analyzer.generate_alignment_llm(
                target_date,
                state,
                trends,
                graph,
                active_goals,
                record_texts,
            )
            if debug:
                timing["llm_ms"] = int((time.monotonic() - llm_start) * 1000)
            if llm_result:
                if isinstance(llm_result.get("snapshot"), str):
                    snapshot = llm_result.get("snapshot")
                if isinstance(llm_result.get("pattern"), str):
                    pattern = llm_result.get("pattern")
                raw_board = llm_result.get("value_board")
                if isinstance(raw_board, list):
                    cleaned = []
                    for item in raw_board:
                        if not isinstance(item, dict):
                            continue
                        value = str(item.get("value") or "").strip()
                        role = str(item.get("role") or "").strip()
                        trend = str(item.get("trend") or "").strip()
                        summary = str(item.get("summary") or "").strip()
                        if not value or not summary:
                            continue
                        cleaned.append(
                            {
                                "value": value,
                                "role": role if role in {"main", "sub"} else "sub",
                                "trend": trend if trend in {"up", "down", "flat"} else "flat",
                                "summary": summary,
                            }
                        )
                    if cleaned:
                        value_board = cleaned
                raw_focus = llm_result.get("focus")
                if isinstance(raw_focus, dict):
                    name = str(raw_focus.get("name") or "").strip()
                    intent = str(raw_focus.get("intent") or "").strip()
                    why = str(raw_focus.get("why") or "").strip()
                    if name or intent or why:
                        focus = {"name": name, "intent": intent, "why": why}
            # Fallback to mock if LLM returns empty
            if not value_board and not pattern:
                mock_data = _mock_alignment_result()
                pattern = mock_data.get("pattern")
                value_board = mock_data.get("value_board", [])
                focus = mock_data.get("focus")
        except Exception:
            # Use mock data on LLM failure
            mock_data = _mock_alignment_result()
            pattern = mock_data.get("pattern")
            value_board = mock_data.get("value_board", [])
            focus = mock_data.get("focus")

    # Fallback: if no value_board, generate defaults from active_goals
    if not value_board and active_goals:
        value_board = [
            {
                "value": active_goals[0],
                "role": "main",
                "trend": "flat",
                "summary": "Tracking in progress",
            }
        ]
        if len(active_goals) > 1:
            value_board.append(
                {
                    "value": active_goals[1],
                    "role": "sub",
                    "trend": "flat",
                    "summary": "Tracking in progress",
                }
            )

    if debug:
        timing["total_ms"] = int((time.monotonic() - total_start) * 1000)

    response = {
        "date": target_date.isoformat(),
        "metrics": metrics,
        "snapshot": snapshot,
        "pattern": pattern,
        "active_goals": active_goals,
        "goal_options": goal_options,
        "value_board": value_board,
        "focus": focus,
    }
    if debug:
        response["timing"] = timing

    _save_ob_display_data("alignment", response)

    return response


@app.post("/alignment/goals")
async def alignment_goals(payload: dict, request: Request):
    if not _authorized(request, payload):
        return _error(401, "unauthorized")
    active = payload.get("active") or payload.get("active_goals")
    if isinstance(active, list):
        _save_active_goals([str(item) for item in active if item is not None])
    return {
        "active_goals": _load_active_goals(),
        "goal_options": _load_goal_options(),
    }


@app.post("/alignment/focus")
async def alignment_focus(payload: dict, request: Request):
    """Get or set the weekly focus."""
    if not _authorized(request, payload):
        return _error(401, "unauthorized")
    date_str = payload.get("date")
    try:
        target_date = datetime.fromisoformat(date_str).date() if date_str else datetime.now().date()
    except Exception:
        return _error(400, "invalid date")

    action = payload.get("action")  # "get", "set", "options"

    if action == "set":
        focus = payload.get("focus")
        if not focus or not isinstance(focus, dict):
            return _error(400, "missing focus")
        _save_weekly_focus(target_date, focus)
        return {
            "week": _get_week_key(target_date),
            "focus": focus,
            "status": "saved",
        }

    elif action == "options":
        active_goals = _load_active_goals()
        options = _generate_focus_options(active_goals, {})
        return {
            "week": _get_week_key(target_date),
            "options": options,
        }

    else:  # default: get
        saved = _load_weekly_focus(target_date)
        if saved:
            return {
                "week": _get_week_key(target_date),
                "focus": saved.get("focus"),
                "selected_at": saved.get("selected_at"),
                "has_focus": True,
            }
        else:
            active_goals = _load_active_goals()
            options = _generate_focus_options(active_goals, {})
            return {
                "week": _get_week_key(target_date),
                "focus": None,
                "has_focus": False,
                "options": options,
            }


@app.post("/morning")
async def morning(payload: dict, request: Request):
    if not _authorized(request, payload):
        return _error(401, "unauthorized")
    debug = bool(payload.get("debug"))
    skip_llm = bool(payload.get("skip_llm"))
    timing: dict[str, int] = {}
    total_start = time.monotonic()
    date_str = payload.get("date")
    text_input = payload.get("text") or payload.get("note")
    try:
        date = datetime.fromisoformat(date_str).date() if date_str else datetime.now().date()
    except Exception:
        return _error(400, "invalid date")
    try:
        file_start = time.monotonic()
        path = manage_day.ensure_daily_file(date)
        if text_input:
            manage_day.append_journal_entry(path, "Morning Check-in", text_input)
        if debug:
            timing["file_write_ms"] = int((time.monotonic() - file_start) * 1000)

        graph = {}
        try:
            graph_start = time.monotonic()
            graph = goal_manager.build_goal_graph()
            goal_manager.save_goal_graph(graph)
            if debug:
                timing["goal_graph_ms"] = int((time.monotonic() - graph_start) * 1000)
        except Exception:
            graph = {}

        llm_result = None
        use_mock = bool(payload.get("mock"))
        if not skip_llm:
            try:
                state_start = time.monotonic()
                state = state_recorder.load_daily_state(date)
                if debug:
                    timing["load_state_ms"] = int((time.monotonic() - state_start) * 1000)
                trends_start = time.monotonic()
                trends = state_analytics.summarize_multi_windows(date)
                if debug:
                    timing["trends_ms"] = int((time.monotonic() - trends_start) * 1000)
                llm_start = time.monotonic()
                llm_result = llm_analyzer.generate_morning_llm(
                    date,
                    state,
                    trends,
                    graph,
                    {"text": text_input, "active_goals": _load_active_goals()},
                )
                if debug:
                    timing["llm_ms"] = int((time.monotonic() - llm_start) * 1000)
            except Exception:
                llm_result = None

        # Fallback to mock data if LLM failed or mock requested
        if llm_result is None and (use_mock or skip_llm):
            llm_result = _mock_morning_result()

        suggestions: list[dict[str, Any]] = []
        ideas: list[str] = []
        micro_action: dict[str, Any] | None = None
        if llm_result:
            def _as_str_list(val: Any) -> list[str]:
                if isinstance(val, str):
                    return [val] if val.strip() else []
                return [s for s in (val or []) if isinstance(s, str)]

            tasks = _as_str_list(llm_result.get("tasks"))
            advice = _as_str_list(llm_result.get("advice"))
            ideas = _as_str_list(llm_result.get("ideas"))
            alignment_note = llm_result.get("alignment_note")

            micro_text = None
            if advice:
                micro_text = advice.pop(0)

            if micro_text:
                micro_id = uuid.uuid4().hex
                suggestions.append(
                    {
                        "id": micro_id,
                        "type": "micro",
                        "text": micro_text,
                        "source": alignment_note if isinstance(alignment_note, str) else None,
                        "related_goal": None,
                    }
                )
                manage_day.append_journal_entry(path, "Micro-Adjustment", micro_text)
                micro_action = {
                    "id": micro_id,
                    "text": micro_text,
                }
                if isinstance(alignment_note, str) and alignment_note.strip():
                    micro_action["aligned_with"] = alignment_note.strip()

            if tasks:
                manage_day.append_gtd_tasks(path, tasks)

        state = state_recorder.load_daily_state(date) or {}
        normalized = state.get("normalized") or {}
        response = {
            "file": str(path),
            "action": "morning",
            "status": _status_from_normalized(normalized),
            "suggestions": suggestions,
            "micro_action": micro_action,
            "ideas": ideas,
        }
        if debug:
            timing["total_ms"] = int((time.monotonic() - total_start) * 1000)
            response["timing"] = timing

        _save_ob_display_data("today", {
            "date": date.isoformat(),
            "micro_action": micro_action,
            "ideas": ideas,
        })

        return response
    except Exception as exc:
        traceback.print_exc()
        return _error(500, str(exc))


@app.post("/evening")
async def evening(payload: dict, request: Request):
    if not _authorized(request, payload):
        return _error(401, "unauthorized")
    debug = bool(payload.get("debug"))
    skip_llm = bool(payload.get("skip_llm"))
    timing: dict[str, int] = {}
    total_start = time.monotonic()
    date_str = payload.get("date")
    journal = payload.get("journal") or payload.get("text")
    mood = payload.get("mood")
    mood_note = payload.get("mood_note")
    energy_drain = payload.get("energy_drain")
    achievement = payload.get("achievement")
    follow_up = payload.get("follow_up")
    reflection_input = payload.get("reflection")
    did = payload.get("did")
    reason = payload.get("reason")
    extra_parts = []
    if mood:
        extra_parts.append(f"Mood: {mood}")
    if mood_note:
        extra_parts.append(f"Mood note: {mood_note}")
    if energy_drain:
        extra_parts.append(f"Energy drain: {energy_drain}")
    if achievement:
        extra_parts.append(f"Achievement: {achievement}")
    if follow_up:
        extra_parts.append(f"Follow-up: {follow_up}")
    if reflection_input:
        extra_parts.append(f"Reflection: {reflection_input}")

    journal_text = ""
    if isinstance(journal, str) and journal.strip():
        journal_text = journal.strip()
    if extra_parts:
        journal_text = "\n".join([journal_text] + extra_parts) if journal_text else "\n".join(extra_parts)

    if not journal_text:
        return _error(400, "missing journal")
    try:
        date = datetime.fromisoformat(date_str).date() if date_str else datetime.now().date()
    except Exception:
        return _error(400, "invalid date")
    try:
        file_start = time.monotonic()
        path = manage_day.ensure_daily_file(date)
        manage_day.append_journal_entry(path, "Evening Summary", journal_text)

        if did is not None:
            did_text = str(did).strip().lower()
            if did_text in {"yes", "true", "1"}:
                review = "Yes"
            elif did_text in {"no", "false", "0"}:
                review = "No"
            else:
                review = str(did).strip()
            if reason:
                manage_day.append_journal_entry(path, "Practice Review", f"Review: {review} (Reason: {reason})")
            else:
                manage_day.append_journal_entry(path, "Practice Review", f"Review: {review}")
        if debug:
            timing["file_write_ms"] = int((time.monotonic() - file_start) * 1000)

        graph = {}
        try:
            graph_start = time.monotonic()
            graph = goal_manager.build_goal_graph()
            goal_manager.save_goal_graph(graph)
            if debug:
                timing["goal_graph_ms"] = int((time.monotonic() - graph_start) * 1000)
        except Exception:
            graph = {}

        llm_result = None
        try:
            record_start = time.monotonic()
            records = record_store.load_records(date)
            record_texts = record_store.summarize_records(records)
            if debug:
                timing["records_ms"] = int((time.monotonic() - record_start) * 1000)
        except Exception:
            record_texts = []
        use_mock = bool(payload.get("mock"))
        if not skip_llm:
            try:
                llm_start = time.monotonic()
                llm_result = llm_analyzer.generate_evening_llm(
                    date,
                    journal_text,
                    record_texts,
                    graph,
                )
                if debug:
                    timing["llm_ms"] = int((time.monotonic() - llm_start) * 1000)
            except Exception:
                llm_result = None

        # Fallback to mock data if LLM failed or mock requested
        if llm_result is None and (use_mock or skip_llm):
            llm_result = _mock_evening_result()

        analysis: dict[str, Any] = {}
        tomorrow_text = None
        if llm_result:
            summary = llm_result.get("summary")
            if isinstance(summary, str) and summary.strip():
                analysis["summary"] = summary.strip()
            mood = llm_result.get("mood")
            if isinstance(mood, str) and mood.strip():
                analysis["mood"] = mood.strip()
            topics = llm_result.get("topics")
            if isinstance(topics, list):
                clean_topics = [t.strip() for t in topics if isinstance(t, str) and t.strip()]
                if clean_topics:
                    analysis["topics"] = clean_topics
            elif isinstance(topics, str) and topics.strip():
                analysis["topics"] = [topics.strip()]
            linked_projects = llm_result.get("linked_projects")
            if isinstance(linked_projects, list):
                clean_projects = [p.strip() for p in linked_projects if isinstance(p, str) and p.strip()]
                if clean_projects:
                    analysis["linked_projects"] = clean_projects
            elif isinstance(linked_projects, str) and linked_projects.strip():
                analysis["linked_projects"] = [linked_projects.strip()]
            reflection = llm_result.get("reflection")
            if isinstance(reflection, str) and reflection.strip():
                analysis["reflection"] = reflection.strip()

            def _as_str_list_ev(val: Any) -> list[str]:
                if isinstance(val, str):
                    return [val] if val.strip() else []
                return [s for s in (val or []) if isinstance(s, str)]

            tomorrow_tasks = _as_str_list_ev(llm_result.get("tomorrow_tasks"))
            advice = _as_str_list_ev(llm_result.get("advice"))
            if tomorrow_tasks:
                tomorrow_text = tomorrow_tasks[0].strip()
            elif advice:
                tomorrow_text = advice[0].strip()

        response = {
            "file": str(path),
            "action": "evening",
            "analysis": analysis,
            "tomorrow_advice": tomorrow_text,
            "tomorrow_suggestions": (
                [
                    {
                        "id": uuid.uuid4().hex,
                        "type": "tomorrow",
                        "text": tomorrow_text,
                    }
                ]
                if tomorrow_text
                else []
            ),
        }
        if debug:
            timing["total_ms"] = int((time.monotonic() - total_start) * 1000)
            response["timing"] = timing

        _save_ob_display_data("night", {
            "date": date.isoformat(),
            "analysis": analysis,
            "tomorrow_advice": tomorrow_text,
        })

        return response
    except Exception as exc:
        traceback.print_exc()
        return _error(500, str(exc))


@app.post("/record")
async def record(payload: dict, request: Request):
    if not _authorized(request, payload):
        return _error(401, "unauthorized")
    text = payload.get("text")
    date_str = payload.get("date")
    if not text:
        return _error(400, "missing text")
    try:
        date = datetime.fromisoformat(date_str).date() if date_str else datetime.now().date()
    except Exception:
        return _error(400, "invalid date")
    try:
        path = record_store.add_record(date, text, source="ui")
        daily_path = None
        try:
            daily_path = manage_day.ensure_daily_file(date)
            manage_day.append_journal_entry(daily_path, "Record", text)
        except Exception:
            daily_path = None
        return {
            "saved": str(path),
            "action": "record",
            "daily_updated": str(daily_path) if daily_path else None,
        }
    except Exception as exc:
        traceback.print_exc()
        return _error(500, str(exc))


@app.post("/suggestion/action")
async def suggestion_action(payload: dict, request: Request):
    if not _authorized(request, payload):
        return _error(401, "unauthorized")
    action = str(payload.get("action") or "").strip().lower()
    suggestion_id = payload.get("suggestion_id")
    suggestion_text = payload.get("text") or payload.get("suggestion_text")
    suggestion_type = payload.get("type") or payload.get("suggestion_type")
    modified_text = payload.get("modified_text")
    date_str = payload.get("date")

    try:
        date = datetime.fromisoformat(date_str).date() if date_str else datetime.now().date()
    except Exception:
        return _error(400, "invalid date")

    label_map = {"adopt": "Adopted", "ignore": "Ignored", "modify": "Modified"}
    action_label = label_map.get(action, action)

    display_text = None
    if action == "modify" and isinstance(modified_text, str) and modified_text.strip():
        display_text = modified_text.strip()
        if isinstance(suggestion_text, str) and suggestion_text.strip():
            display_text = f"{display_text} (original: {suggestion_text.strip()})"
    elif isinstance(suggestion_text, str) and suggestion_text.strip():
        display_text = suggestion_text.strip()
    elif suggestion_id:
        display_text = f"Suggestion ID {suggestion_id}"

    try:
        path = manage_day.ensure_daily_file(date)
        if display_text:
            suffix = f"{action_label}: {display_text}"
        else:
            suffix = f"{action_label}"
        if suggestion_type:
            suffix = f"{suffix} (type: {suggestion_type})"
        manage_day.append_journal_entry(path, "Practice Review", suffix)
    except Exception:
        pass

    try:
        _append_jsonl(
            SUGGESTION_ACTION_LOG,
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "date": date.isoformat(),
                "action": action,
                "suggestion_id": suggestion_id,
                "suggestion_type": suggestion_type,
                "text": suggestion_text,
                "modified_text": modified_text,
            },
        )
    except Exception:
        pass

    return {"status": "ok"}


@app.post("/garmin")
async def garmin(payload: dict, request: Request):
    if not _authorized(request, payload):
        return _error(401, "unauthorized")
    date_str = payload.get("date")
    update_note = bool(payload.get("update_note"))
    if date_str and _parse_date(date_str) is None:
        return _error(400, "invalid date")
    try:
        target_date = _parse_date(date_str) or (datetime.now().date() - timedelta(days=1))
        raw = ui_server._fetch_garmin_payload(target_date)
    except Exception as exc:
        traceback.print_exc()
        return _error(500, str(exc))

    try:
        out_dir = GARMIN_ROOT / target_date.strftime("%Y%m%d")
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%H%M%S")
        file_name = f"garmin_{target_date.isoformat()}_{ts}.json"
        saved_path = out_dir / file_name
        _write_json(saved_path, raw)

        state = state_recorder.build_daily_state_from_garmin(target_date, raw)
        existing = state_recorder.load_daily_state(target_date)
        merged = state_recorder.merge_daily_state(existing, state)
        state_path = state_recorder.save_daily_state(merged)

        daily_path = None
        if update_note:
            daily_path = manage_day.ensure_daily_file(target_date)
            manage_day.update_device_data(daily_path, merged.get("normalized") or {})

        try:
            _append_jsonl(
                SYNC_LOG_PATH,
                {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "source": "garmin",
                    "date": target_date.isoformat(),
                    "file": file_name,
                    "ok": True,
                },
            )
        except Exception:
            pass
        return {
            "action": "garmin",
            "date": target_date.isoformat(),
            "saved": str(saved_path),
            "state_saved": str(state_path),
            "daily_updated": str(daily_path) if daily_path else None,
            "status": _status_from_normalized(merged.get("normalized") or {}),
        }
    except Exception as exc:
        traceback.print_exc()
        return _error(500, str(exc))


@app.post("/vision")
async def vision(payload: dict, request: Request):
    if not _authorized(request, payload):
        return _error(401, "unauthorized")
    image_urls = payload.get("image_urls") or []
    image_b64_list = payload.get("image_b64_list") or []
    if not image_urls and not image_b64_list:
        return _error(400, "missing image_urls or image_b64_list")

    prompt_override = payload.get("prompt")
    if prompt_override:
        prompt = prompt_override
        prompt_source = "payload"
        prompt_path = None
        prompt_version = "payload"
    elif ui_server.VISION_PROMPT_OVERRIDE:
        prompt = ui_server.VISION_PROMPT_OVERRIDE
        prompt_source = "file"
        prompt_path = str(ui_server.VISION_PROMPT_PATH)
        prompt_version = ui_server.VISION_PROMPT_PATH.stem
    else:
        prompt = ui_server.ChatHandler.default_vision_prompt
        prompt_source = "builtin"
        prompt_path = None
        prompt_version = "builtin"

    provider = payload.get("provider") or "ark"
    model = payload.get("model") or chat_bot.DEFAULT_VISION_MODEL
    date_str = payload.get("date")
    try:
        capture_date = datetime.fromisoformat(date_str).date() if date_str else datetime.now().date() - timedelta(days=1)
    except Exception:
        return _error(400, "invalid date")

    try:
        client = chat_bot.make_client(provider)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        data_urls: list[str] = []
        if image_b64_list:
            for image_b64 in image_b64_list:
                try:
                    base64.b64decode(image_b64, validate=True)
                except Exception:
                    return _error(400, "invalid base64 in image_b64_list")
                data_urls.append(f"data:image/jpeg;base64,{image_b64}")
        all_urls = data_urls + image_urls
        text = chat_bot.vision_describe_multi(client, model, all_urls, prompt)
        saved_imgs = ui_server.save_images_from_base64(image_b64_list, ts)
        saved_path = ui_server.save_vision_result(
            provider=provider,
            model=model,
            capture_date=capture_date,
            prompt=prompt,
            urls=all_urls,
            result_text=text,
            prompt_source=prompt_source,
            prompt_path=prompt_path,
            prompt_version=prompt_version,
        )
        status_path = None
        state_path = None
        daily_path = None
        try:
            result_data = json.loads(text)
            state = state_recorder.build_daily_state(capture_date, vision_result=result_data)
            existing = state_recorder.load_daily_state(capture_date)
            merged = state_recorder.merge_daily_state(existing, state)
            state_path = state_recorder.save_daily_state(merged)
            daily_path = manage_day.ensure_daily_file(capture_date)
            manage_day.update_device_data(daily_path, merged.get("normalized") or {})
            if ui_server.ALLOW_STATUS_WRITE:
                status_path = ui_server.update_month_status(capture_date, result_data)
        except Exception:
            pass
        return {
            "vision": text,
            "provider": provider,
            "model": model,
            "capture_date": capture_date.isoformat(),
            "saved": str(saved_path),
            "status_updated": str(status_path) if status_path else None,
            "state_saved": str(state_path) if state_path else None,
            "daily_updated": str(daily_path) if daily_path else None,
            "images_saved": [str(p) for p in saved_imgs],
            "image_urls": image_urls,
        }
    except Exception as exc:
        traceback.print_exc()
        return _error(500, str(exc))


@app.post("/ingest")
async def ingest(payload: UploadPayload, update_note: bool = Query(default=False)) -> dict[str, Any]:
    payload_dict = _model_dump(payload)
    target_date = (
        _parse_date(payload_dict.get("localDate") or payload_dict.get("local_date"))
        or _parse_iso_date(payload_dict.get("rangeStart"))
        or _parse_iso_date(payload_dict.get("rangeEnd"))
        or _parse_iso_date(payload_dict.get("generatedAt"))
        or datetime.now(timezone.utc).date()
    )

    out_dir = MOBILE_ROOT / target_date.strftime("%Y%m%d")
    out_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"{payload.deviceId}_{uuid.uuid4().hex}.json"
    file_path = out_dir / file_name
    _write_json(file_path, payload_dict)

    state = state_recorder.build_daily_state_from_mobile(target_date, payload_dict)
    existing = state_recorder.load_daily_state(target_date)
    merged = state_recorder.merge_daily_state(existing, state)
    state_path = state_recorder.save_daily_state(merged)

    daily_path = _update_note(target_date, merged.get("normalized") or {}, update_note or AUTO_UPDATE_NOTE)
    try:
        _append_jsonl(
            SYNC_LOG_PATH,
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "source": "mobile",
                "date": target_date.isoformat(),
                "file": file_name,
                "device_id": payload.deviceId,
                "ok": True,
            },
        )
    except Exception:
        pass
    return {
        "status": "ok",
        "file": file_name,
        "state": str(state_path),
        "note": str(daily_path) if daily_path else None,
        "metrics": _status_from_normalized(merged.get("normalized") or {}),
    }


@app.post("/ingest/garmin")
async def ingest_garmin(payload: dict, update_note: bool = Query(default=False)) -> dict[str, Any]:
    date_str = payload.get("date")
    if not date_str:
        date_str = ((payload.get("data") or {}).get("sleep") or {}).get("dailySleepDTO", {}).get("calendarDate")
    target_date = _parse_iso_date(date_str) or datetime.now(timezone.utc).date()

    out_dir = GARMIN_ROOT / target_date.strftime("%Y%m%d")
    out_dir.mkdir(parents=True, exist_ok=True)
    utc_now = datetime.now(timezone.utc)
    file_name = f"garmin_{target_date.isoformat()}_{utc_now.strftime('%H%M%S')}.json"
    file_path = out_dir / file_name
    _write_json(file_path, payload)

    state = state_recorder.build_daily_state_from_garmin(target_date, payload)
    existing = state_recorder.load_daily_state(target_date)
    merged = state_recorder.merge_daily_state(existing, state)
    state_path = state_recorder.save_daily_state(merged)

    daily_path = _update_note(target_date, merged.get("normalized") or {}, update_note or AUTO_UPDATE_NOTE)
    try:
        _append_jsonl(
            SYNC_LOG_PATH,
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "source": "garmin_ingest",
                "date": target_date.isoformat(),
                "file": file_name,
                "ok": True,
            },
        )
    except Exception:
        pass
    return {
        "status": "ok",
        "file": file_name,
        "state": str(state_path),
        "note": str(daily_path) if daily_path else None,
        "metrics": _status_from_normalized(merged.get("normalized") or {}),
    }
