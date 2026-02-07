#!/usr/bin/env python3
"""Daily note helper for Obsidian vault.

Creates or updates a daily Markdown in one place:
- Morning: ensure file exists, add suggested todos, OCR metrics placeholders, text input.
- Evening: append diary text and summary.

GPT API/OCR hooks are stubbed; fill in your keys and logic where marked.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

from core import (
    advisor,
    goal_manager,
    journal_analyzer,
    llm_analyzer,
    record_store,
    state_analytics,
    state_recorder,
)
from integrations.obsidian import (
    ObsidianPaths,
    append_list_items,
    ensure_daily_file as obsidian_ensure_daily_file,
    render_template,
    replace_or_append_section,
    safe_write_text,
    update_subsection_in_section,
    update_frontmatter,
)
from integrations.config import get_config

OBSIDIAN_PATHS = ObsidianPaths.from_config()
SECTION_RE_CACHE: Dict[str, re.Pattern[str]] = {}
LEGACY_WEEKLY_MARKER_START = "<!-- AUTO:weekly-tasks:start -->"
LEGACY_WEEKLY_MARKER_END = "<!-- AUTO:weekly-tasks:end -->"
JOURNAL_SECTION_HEADING = "Journal"
GTD_SECTION_HEADING = "GTD"
GTD_TODAY_HEADING = "Today's Tasks"


def _section_pattern(heading: str, level: int = 2) -> re.Pattern[str]:
    key = f"{level}:{heading}"
    if key not in SECTION_RE_CACHE:
        SECTION_RE_CACHE[key] = re.compile(
            rf"(^{ '#' * level }\s+{re.escape(heading)}\s*\n)(.*?)(?=^#{{1,{level}}}\s|\Z)",
            re.DOTALL | re.MULTILINE,
        )
    return SECTION_RE_CACHE[key]


def ensure_daily_file(date: dt.date) -> Path:
    """Create daily file if missing and return its path."""
    return obsidian_ensure_daily_file(date, OBSIDIAN_PATHS)


def _get_week_paths() -> tuple[Optional[Path], Optional[Path], Optional[Path]]:
    cfg = get_config()
    week_root_value = cfg.get("diary_week_root")
    if not week_root_value:
        return None, None, None
    week_root = Path(str(week_root_value)).expanduser()
    template_value = cfg.get("weekly_template_path")
    template_path = Path(str(template_value)).expanduser() if template_value else None
    write_root_value = cfg.get("week_write_root")
    write_root = Path(str(write_root_value)).expanduser() if write_root_value else week_root
    return week_root, template_path, write_root


def ensure_weekly_file(date: dt.date) -> Optional[Path]:
    week_root, template_path, write_root = _get_week_paths()
    if not week_root:
        return None
    week_root.mkdir(parents=True, exist_ok=True)
    iso = date.isocalendar()
    iso_year = iso.year if hasattr(iso, "year") else iso[0]
    iso_week = iso.week if hasattr(iso, "week") else iso[1]
    week_id = f"{iso_year}-W{iso_week}"
    path = week_root / f"{week_id}.md"
    if path.exists():
        return path
    legacy_week_id = f"{iso_year}-W{iso_week:02d}"
    legacy_path = week_root / f"{legacy_week_id}.md"
    if legacy_path.exists():
        return legacy_path
    template_text = None
    if template_path and template_path.exists():
        template_text = template_path.read_text(encoding="utf-8")
        template_text = render_template(template_text, date)
    if template_text is None:
        template_text = (
            "---\n"
            "journal: week\n"
            f"journal-week: {week_id}\n"
            "---\n\n"
            "# Weekly Tasks\n"
        )
    safe_write_text(path, template_text, OBSIDIAN_PATHS.backup_root, write_root)
    return path


def call_gpt_ocr(image_paths: List[Path]) -> Dict[str, str]:
    """Stub for OCR via GPT-5. Fill in with your API call."""
    # TODO: Implement GPT-5 vision call here. Return key/value metrics.
    if not image_paths:
        return {}
    return {str(p): "TODO: OCR result" for p in image_paths}


def format_state_block(
    ocr_metrics: Dict[str, str],
    text_input: Optional[str] = None,
) -> str:
    """Render status record body."""
    parts = []
    if text_input:
        parts.append(f"- Note: {text_input}")
    if ocr_metrics:
        parts.append("- Device:")
        for key, val in ocr_metrics.items():
            parts.append(f"  - {key}: {val}")
    if not parts:
        parts.append("- (pending)")
    return "\n".join(parts) + "\n"


def _format_minutes(minutes: Optional[int]) -> str:
    if minutes is None:
        return "-"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}:{mins:02d}"


def format_device_data_block(normalized: Dict[str, object]) -> str:
    phone = normalized.get("phone_usage") or {}
    sleep = normalized.get("sleep") or {}
    lines = []

    sleep_bits = []
    total = sleep.get("total_minutes")
    if total is not None:
        sleep_bits.append(f"Total {_format_minutes(total)}")
    deep = sleep.get("deep_minutes")
    if deep is not None:
        sleep_bits.append(f"Deep {_format_minutes(deep)}")
    rem = sleep.get("rem_minutes")
    if rem is not None:
        sleep_bits.append(f"REM {_format_minutes(rem)}")
    score = sleep.get("score")
    if score is not None:
        sleep_bits.append(f"Score {score}")
    lines.append(f"- Sleep: {' '.join(sleep_bits) if sleep_bits else '-'}")

    screen_minutes = phone.get("screen_time_minutes")
    lines.append(f"- Screen Time: {_format_minutes(screen_minutes) if screen_minutes is not None else '-'}")

    night_minutes = phone.get("night_screen_minutes")
    lines.append(f"- Night Screen: {_format_minutes(night_minutes) if night_minutes is not None else '-'}")

    unlock_count = phone.get("unlock_count")
    lines.append(f"- Unlocks: {unlock_count if unlock_count is not None else '-'}")

    apps = phone.get("top_apps") or []
    app_bits = []
    for entry in apps:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        minutes = entry.get("minutes")
        if name and minutes is not None:
            app_bits.append(f"{name} {_format_minutes(int(minutes))}")
        elif name:
            app_bits.append(name)
    lines.append(f"- Top Apps: {' / '.join(app_bits) if app_bits else '-'}")

    night_apps = phone.get("night_top_apps") or []
    night_bits = []
    for entry in night_apps:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        minutes = entry.get("minutes")
        if name and minutes is not None:
            night_bits.append(f"{name} {_format_minutes(int(minutes))}")
        elif name:
            night_bits.append(name)
    lines.append(f"- Night Apps: {' / '.join(night_bits) if night_bits else '-'}")

    hrv = normalized.get("hrv_ms")
    lines.append(f"- HRV: {hrv if hrv is not None else '-'}")
    resting = normalized.get("resting_bpm")
    lines.append(f"- Resting HR: {resting if resting is not None else '-'}")
    spo2 = normalized.get("spo2_percent")
    lines.append(f"- SpO2: {spo2 if spo2 is not None else '-'}")
    stress = normalized.get("stress_level")
    lines.append(f"- Stress: {stress if stress is not None else '-'}")

    return "\n".join(lines) + "\n"


def update_device_data(path: Path, normalized: Dict[str, object]) -> None:
    text = path.read_text(encoding="utf-8")
    device_body = format_device_data_block(normalized)
    text = update_subsection_in_section(text, "Status", "Device Data", device_body)
    backup_path = safe_write_text(path, text, OBSIDIAN_PATHS.backup_root, OBSIDIAN_PATHS.write_root)
    if backup_path:
        print(f"[backup] {backup_path}")


def generate_todo_suggestions(goal_text: Optional[str], text_input: Optional[str]) -> List[str]:
    """Generate actionable items from local goals/projects, fallback to generic hints."""
    try:
        graph = goal_manager.build_goal_graph()
        goal_manager.save_goal_graph(graph)
        suggestions = advisor.generate_daily_actions(graph, limit=3)
        if suggestions:
            return suggestions
    except Exception:
        pass
    suggestions: List[str] = []
    if goal_text:
        suggestions.append("Break down 1 actionable step from long-term goals")
    if text_input:
        suggestions.append("Choose a task that fits your current energy level")
    if not suggestions:
        suggestions.append("Write down the 3 most important things for today")
    return suggestions


def generate_advice_suggestions(date: dt.date, text_input: Optional[str]) -> List[str]:
    """Generate softer advice based on recent state and stored metrics."""
    try:
        state = state_recorder.load_daily_state(date)
        trends = state_analytics.summarize_multi_windows(date)
        return advisor.generate_daily_advice(state, text_input, limit=2, trends=trends)
    except Exception:
        return ["Smile more, give yourself some lightness"]


def generate_evening_advice(date: dt.date, text_input: Optional[str]) -> List[str]:
    """Generate evening advice (fallback) based on state + text."""
    try:
        state = state_recorder.load_daily_state(date)
        trends = state_analytics.summarize_multi_windows(date)
        advice = advisor.generate_daily_advice(state, text_input, limit=3, trends=trends)
        return advice if advice else ["Slow down tonight, give yourself some recovery time"]
    except Exception:
        return ["Slow down tonight, give yourself some recovery time"]


def generate_tomorrow_tasks(graph: Optional[Dict[str, object]], limit: int = 3) -> List[str]:
    """Generate next-day tasks (fallback) from active goals/projects."""
    if not graph:
        return ["Write down the 3 most important things for tomorrow"]
    suggestions = advisor.generate_daily_actions(graph, limit=limit)
    return suggestions if suggestions else ["Write down the 3 most important things for tomorrow"]


def _parse_date(date_str: Optional[str]) -> Optional[dt.date]:
    if not date_str:
        return None
    try:
        return dt.date.fromisoformat(date_str)
    except Exception:
        return None


def _extract_section_body(text: str, heading: str, level: int = 2) -> str:
    pattern = _section_pattern(heading, level)
    match = pattern.search(text)
    if not match:
        return ""
    return match.group(2).rstrip()


def _extract_subsection_body(
    text: str,
    section_heading: str,
    subsection_heading: str,
    section_level: int = 2,
    subsection_level: int = 3,
) -> str:
    section_match = _section_pattern(section_heading, section_level).search(text)
    if not section_match:
        return ""
    section_body = section_match.group(2)
    return _extract_section_body(section_body, subsection_heading, subsection_level)


def _append_subsection_item(
    text: str,
    section_heading: str,
    subsection_heading: str,
    item: str,
    section_level: int = 2,
    subsection_level: int = 3,
) -> str:
    existing_body = _extract_subsection_body(text, section_heading, subsection_heading, section_level, subsection_level)
    updated_body = append_list_items(existing_body, [item]).rstrip() + "\n"
    return update_subsection_in_section(
        text,
        section_heading,
        subsection_heading,
        updated_body,
        section_level=section_level,
        subsection_level=subsection_level,
    )


def append_journal_entry(
    path: Path,
    subsection_heading: str,
    content: str,
    timestamp: Optional[dt.datetime] = None,
) -> None:
    cleaned = content.strip()
    if not cleaned:
        return
    stamp = (timestamp or dt.datetime.now()).strftime("%H:%M")
    entry = f"[{stamp}] {cleaned}"
    text = path.read_text(encoding="utf-8")
    text = _append_subsection_item(text, JOURNAL_SECTION_HEADING, subsection_heading, entry)
    backup_path = safe_write_text(path, text, OBSIDIAN_PATHS.backup_root, OBSIDIAN_PATHS.write_root)
    if backup_path:
        print(f"[backup] {backup_path}")


def append_gtd_tasks(
    path: Path,
    tasks: List[str],
    section_heading: str = GTD_SECTION_HEADING,
    subsection_heading: str = GTD_TODAY_HEADING,
) -> None:
    normalized = _normalize_tasks(tasks)
    if not normalized:
        return
    text = path.read_text(encoding="utf-8")
    existing_body = _extract_subsection_body(
        text,
        section_heading,
        subsection_heading,
        section_level=1,
        subsection_level=2,
    )
    merged_body = _merge_task_body(existing_body, normalized)
    text = update_subsection_in_section(
        text,
        section_heading,
        subsection_heading,
        merged_body,
        section_level=1,
        subsection_level=2,
    )
    backup_path = safe_write_text(path, text, OBSIDIAN_PATHS.backup_root, OBSIDIAN_PATHS.write_root)
    if backup_path:
        print(f"[backup] {backup_path}")


def _merge_task_body(existing_body: str, tasks: List[str]) -> str:
    if not tasks:
        return existing_body
    task_re = re.compile(r"^- \[[ xX]\]\s+(.*)$")
    existing_labels = set()
    for line in existing_body.splitlines():
        match = task_re.match(line.strip())
        if match:
            existing_labels.add(match.group(1).strip())
    new_items = [t.strip() for t in tasks if t and t.strip() and t.strip() not in existing_labels]
    if not new_items:
        return existing_body
    append_body = append_list_items("", [f"[ ] {t}" for t in new_items]).rstrip()
    if existing_body.strip():
        return existing_body.rstrip() + "\n" + append_body + "\n"
    return append_body + "\n"


def _detect_heading_level(text: str, heading: str) -> int:
    for level in (1, 2, 3):
        if _section_pattern(heading, level).search(text):
            return level
    return 1


def _normalize_tasks(items: List[str]) -> List[str]:
    normalized = []
    seen = set()
    for item in items:
        if not item or not isinstance(item, str):
            continue
        text = item.strip()
        if not text:
            continue
        if text.startswith("- ["):
            text = text.split("]", 1)[-1].strip()
        if text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def _normalize_weekly_plan(value: object) -> List[Dict[str, List[str]]]:
    if isinstance(value, list):
        normalized = []
        for entry in value:
            if not isinstance(entry, dict):
                continue
            goal = entry.get("goal")
            tasks = entry.get("tasks")
            if not goal or not isinstance(goal, str):
                continue
            task_list = []
            if isinstance(tasks, list):
                task_list = _normalize_tasks([t for t in tasks if isinstance(t, str)])
            normalized.append({"goal": goal.strip(), "tasks": task_list})
        return normalized
    return []


def _project_label(project: Dict[str, object]) -> Optional[str]:
    name = project.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    target = project.get("target")
    if isinstance(target, str) and target.strip():
        return f"{name.strip()} ({target.strip()})"
    return name.strip()


def _project_task_ref(project: Dict[str, object]) -> Optional[str]:
    name = project.get("id") or project.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    target = project.get("target")
    text = f"#project [[{name.strip()}]]"
    if isinstance(target, str) and target.strip():
        text += f" {target.strip()}"
    return text


def _projects_by_goal(graph: Optional[Dict[str, object]]) -> Dict[str, List[Dict[str, str]]]:
    goals = (graph or {}).get("goals") or []
    projects = (graph or {}).get("projects") or []
    valid_goals = {g.get("name") for g in goals if isinstance(g.get("name"), str)}
    mapping: Dict[str, List[Dict[str, str]]] = {}
    for project in projects:
        status = str(project.get("status", "")).lower()
        if status in advisor.DONE_STATUSES:
            continue
        goal = project.get("goal")
        if goal not in valid_goals:
            continue
        label = _project_label(project)
        task_ref = _project_task_ref(project)
        name = project.get("name")
        if not label or not task_ref or not isinstance(name, str):
            continue
        mapping.setdefault(goal, []).append(
            {
                "id": project.get("id"),
                "name": name,
                "label": label,
                "task": task_ref,
            }
        )
    return mapping


def build_weekly_plan(
    graph: Optional[Dict[str, object]],
    weekly_plan: Optional[List[Dict[str, List[str]]]] = None,
) -> List[Dict[str, List[str]]]:
    mapping = _projects_by_goal(graph)
    plan: List[Dict[str, List[str]]] = []
    used_goals = set()

    if weekly_plan:
        for entry in weekly_plan:
            goal = entry.get("goal")
            if goal not in mapping:
                continue
            label_map = {}
            for item in mapping[goal]:
                label_map[item["name"]] = item["task"]
                label_map[item["label"]] = item["task"]
                if item.get("id"):
                    label_map[item["id"]] = item["task"]
            tasks = []
            for raw in entry.get("tasks") or []:
                if not isinstance(raw, str):
                    continue
                cleaned = raw.strip()
                if cleaned in label_map:
                    tasks.append(label_map[cleaned])
            tasks = _normalize_tasks(tasks)
            if tasks:
                plan.append({"goal": goal, "tasks": tasks})
                used_goals.add(goal)

    for goal, items in mapping.items():
        if goal in used_goals:
            continue
        tasks = [item["task"] for item in items if item.get("task")]
        tasks = _normalize_tasks(tasks)
        if tasks:
            plan.append({"goal": goal, "tasks": tasks})
    return plan


def _render_weekly_tasks(plan: List[Dict[str, List[str]]]) -> str:
    lines: List[str] = []
    idx = 1
    for entry in plan:
        goal = entry.get("goal")
        if not goal:
            continue
        lines.append(f"{idx}. Goal: {goal}")
        tasks = _normalize_tasks(entry.get("tasks") or [])
        for task in tasks:
            lines.append(f"   - [ ] {task}")
        idx += 1
    return "\n".join(lines).rstrip() + ("\n" if lines else "")


def render_weekly_tasks(plan: List[Dict[str, List[str]]]) -> str:
    return _render_weekly_tasks(plan)


def _strip_legacy_weekly_markers(body: str) -> str:
    cleaned = []
    for line in body.splitlines():
        if line.strip() in {LEGACY_WEEKLY_MARKER_START, LEGACY_WEEKLY_MARKER_END}:
            continue
        cleaned.append(line)
    return "\n".join(cleaned).rstrip()


def _upsert_weekly_tasks_section(text: str, plan: List[Dict[str, List[str]]]) -> str:
    heading = "Weekly Tasks"
    level = _detect_heading_level(text, heading)
    body = _extract_section_body(text, heading, level)
    cleaned_body = _strip_legacy_weekly_markers(body)
    content = _render_weekly_tasks(plan).rstrip()
    if content:
        updated_body = content + "\n"
    elif cleaned_body.strip():
        updated_body = cleaned_body.rstrip() + "\n"
    else:
        updated_body = ""
    return replace_or_append_section(text, heading, updated_body, heading_level=level)


def _normalize_list(value: object) -> List[str]:
    if isinstance(value, list):
        return [v.strip() for v in value if isinstance(v, str) and v.strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _normalize_linked_projects(value: object) -> Optional[List[str]]:
    if value is None:
        return None
    items: List[str] = []

    def add_text(text: str) -> None:
        cleaned = text.strip()
        if not cleaned:
            return
        if "\n" in cleaned:
            for line in cleaned.splitlines():
                add_text(line)
            return
        cleaned = re.sub(r"^[-*]\s+", "", cleaned).strip()
        if not cleaned:
            return
        if ("[[" in cleaned or "]]" in cleaned) and ("," in cleaned or "，" in cleaned):
            parts = [p.strip() for p in re.split(r"[，,]", cleaned) if p.strip()]
            if len(parts) > 1:
                for part in parts:
                    add_text(part)
                return
        items.append(cleaned)

    def visit(val: object) -> None:
        if isinstance(val, list):
            for entry in val:
                visit(entry)
        elif isinstance(val, str):
            add_text(val)

    visit(value)
    if not items:
        return None
    seen = set()
    normalized: List[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    return normalized


def run_morning(
    path: Path,
    goal_text: Optional[str],
    image_paths: List[Path],
    text_input: Optional[str] = None,
) -> None:
    text = path.read_text(encoding="utf-8")
    ocr_metrics = call_gpt_ocr(image_paths)
    state_block = format_state_block(ocr_metrics, text_input)
    text = replace_or_append_section(text, "Status", state_block)

    date = dt.date.fromisoformat(path.stem)
    llm_result = None
    try:
        graph = goal_manager.build_goal_graph()
        goal_manager.save_goal_graph(graph)
        state = state_recorder.load_daily_state(date)
        trends = state_analytics.summarize_multi_windows(date)
        llm_result = llm_analyzer.generate_morning_llm(
            date,
            state,
            trends,
            graph,
            {"text": text_input},
        )
    except Exception:
        llm_result = None

    if llm_result and isinstance(llm_result.get("tasks"), list):
        todos = [t for t in llm_result.get("tasks") if isinstance(t, str)]
    else:
        print("[llm_fallback] morning tasks -> rule")
        todos = generate_todo_suggestions(goal_text, text_input)

    todo_body = append_list_items("", [f"[ ] {t}" for t in todos])
    text = replace_or_append_section(text, "Today's Tasks", todo_body)

    if llm_result and isinstance(llm_result.get("advice"), list):
        advice = [a for a in llm_result.get("advice") if isinstance(a, str)]
        align_note = llm_result.get("alignment_note")
        if align_note:
            advice.append(f"Alignment: {align_note}")
    else:
        print("[llm_fallback] morning advice -> rule")
        advice = generate_advice_suggestions(date, text_input)

    advice_body = append_list_items("", advice)
    text = replace_or_append_section(text, "Today's Advice", advice_body)

    backup_path = safe_write_text(path, text, OBSIDIAN_PATHS.backup_root, OBSIDIAN_PATHS.write_root)
    if backup_path:
        print(f"[backup] {backup_path}")


def run_evening(path: Path, journal: Optional[str]) -> None:
    text = path.read_text(encoding="utf-8")

    if journal:
        analysis = {}
        record_texts = []
        record_date = dt.date.fromisoformat(path.stem)
        combined_text = journal.strip()
        try:
            records = record_store.load_records(record_date)
            record_texts = record_store.summarize_records(records)
        except Exception:
            record_texts = []
        if record_texts:
            combined_text = combined_text + "\n" + "\n".join(record_texts)

        llm_result = None
        graph = None
        try:
            graph = goal_manager.build_goal_graph()
            goal_manager.save_goal_graph(graph)
        except Exception:
            graph = None

        try:
            llm_result = llm_analyzer.generate_evening_llm(
                record_date,
                journal,
                record_texts,
                graph or {},
            )
        except Exception:
            llm_result = None

        if llm_result:
            analysis = {
                "summary": llm_result.get("summary"),
                "mood": llm_result.get("mood"),
                "topics": llm_result.get("topics"),
                "linked_projects": llm_result.get("linked_projects"),
            }
            reflection = llm_result.get("reflection") or None
            advice = _normalize_list(llm_result.get("advice"))
            tomorrow_tasks = _normalize_list(llm_result.get("tomorrow_tasks"))
            weekly_plan = _normalize_weekly_plan(llm_result.get("weekly_plan"))
        else:
            print("[llm_fallback] evening summary -> rule")
            reflection = None
            try:
                graph = goal_manager.build_goal_graph()
                goal_manager.save_goal_graph(graph)
                analysis = journal_analyzer.analyze_journal(journal, graph, extra_texts=record_texts)
            except Exception:
                analysis = journal_analyzer.analyze_journal(journal, None, extra_texts=record_texts)
            advice = []
            tomorrow_tasks = []
            weekly_plan = []

        topics = analysis.get("topics")
        if isinstance(topics, str):
            analysis["topics"] = [topics]
        linked = _normalize_linked_projects(analysis.get("linked_projects"))
        analysis["linked_projects"] = linked
        text = update_frontmatter(
            text,
            {
                "mood": analysis.get("mood"),
                "topics": analysis.get("topics"),
                "linked_projects": analysis.get("linked_projects"),
            },
        )
        summary_body = journal_analyzer.format_evening_summary(
            journal,
            analysis,
            records=record_texts,
            reflection=reflection,
        )
        text = replace_or_append_section(text, "Evening Summary", summary_body)

        if not advice:
            advice = generate_evening_advice(record_date, combined_text)
        advice_body = append_list_items("", advice)
        text = replace_or_append_section(text, "Evening Advice", advice_body)

        if not tomorrow_tasks:
            tomorrow_tasks = generate_tomorrow_tasks(graph, limit=3)
        if tomorrow_tasks:
            tomorrow_date = record_date + dt.timedelta(days=1)
            tomorrow_path = ensure_daily_file(tomorrow_date)
            tomorrow_text = tomorrow_path.read_text(encoding="utf-8")
            existing_tasks = _extract_section_body(tomorrow_text, "Today's Tasks")
            merged_tasks = _merge_task_body(existing_tasks, tomorrow_tasks)
            tomorrow_text = replace_or_append_section(tomorrow_text, "Today's Tasks", merged_tasks)
            backup_path = safe_write_text(
                tomorrow_path, tomorrow_text, OBSIDIAN_PATHS.backup_root, OBSIDIAN_PATHS.write_root
            )
            if backup_path:
                print(f"[backup] {backup_path}")

        if record_date.weekday() == 6:
            week_date = record_date + dt.timedelta(days=1)
            week_path = ensure_weekly_file(week_date)
            if week_path:
                weekly_plan = build_weekly_plan(graph, weekly_plan)
                week_text = week_path.read_text(encoding="utf-8")
                week_text = render_template(week_text, week_date)
                week_text = _upsert_weekly_tasks_section(week_text, weekly_plan)
                _, _, week_write_root = _get_week_paths()
                backup_path = safe_write_text(
                    week_path,
                    week_text,
                    OBSIDIAN_PATHS.backup_root,
                    week_write_root or week_path.parent,
                )
                if backup_path:
                    print(f"[backup] {backup_path}")

    backup_path = safe_write_text(path, text, OBSIDIAN_PATHS.backup_root, OBSIDIAN_PATHS.write_root)
    if backup_path:
        print(f"[backup] {backup_path}")


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage daily Obsidian note.")
    parser.add_argument("--date", type=str, help="ISO date, default today")
    parser.add_argument("--morning", action="store_true", help="Morning flow: create/update and add todos/state")
    parser.add_argument("--evening", action="store_true", help="Evening flow: append diary/state")
    parser.add_argument("--text", type=str, help="Morning text input")
    parser.add_argument("--journal", type=str, help="Evening journal text")
    parser.add_argument("--goal-file", type=Path, help="Optional: read goal text from file")
    parser.add_argument("--images", type=Path, nargs="*", help="Optional: image paths for OCR")
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    date = dt.date.fromisoformat(args.date) if args.date else dt.date.today()
    daily_path = ensure_daily_file(date)

    goal_text = args.goal_file.read_text(encoding="utf-8") if args.goal_file and args.goal_file.exists() else None
    images = [p for p in args.images or [] if p.exists()]

    if args.morning:
        run_morning(daily_path, goal_text, images, text_input=args.text)
    if args.evening:
        run_evening(daily_path, args.journal)

    if not args.morning and not args.evening:
        print(f"Daily file ensured at: {daily_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
