from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from integrations.config import get_config

INDEX_FILES = {"Values.md", "Goals.md", "Projects.md"}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _parse_frontmatter(text: str) -> Dict[str, Any]:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    block = parts[1]
    data: Dict[str, Any] = {}
    for line in block.splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        if ":" not in raw:
            continue
        key, value = raw.split(":", 1)
        key = key.strip().lower()
        value = value.strip().strip('"').strip("'")
        if value.startswith("[") and value.endswith("]"):
            items = [v.strip().strip('"').strip("'") for v in value[1:-1].split(",") if v.strip()]
            data[key] = items
        else:
            data[key] = value
    if "tags" not in data and "tag" in data:
        data["tags"] = data["tag"]
    return data


INLINE_FIELD_RE = re.compile(r"\[([A-Za-z]+)\s*::\s*([^\]]+)\]")


def _parse_inline_fields(text: str) -> Dict[str, str]:
    fields: Dict[str, str] = {}
    for match in INLINE_FIELD_RE.findall(text):
        key, value = match
        fields[key.lower()] = value.strip()
    return fields


def _extract_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            if title and title.lower() != "untitled":
                return title
            break
    return fallback


def _extract_link(value: Optional[str]) -> Optional[str]:
    if not value:
        return value
    match = re.search(r"\[\[([^\]|]+)", value)
    if match:
        return match.group(1).strip()
    return value.strip()


def _extract_date(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    match = re.search(r"(\\d{4}-\\d{2}-\\d{2})", value)
    return match.group(1) if match else None


def _as_list(tags: Any) -> List[str]:
    if tags is None:
        return []
    if isinstance(tags, list):
        return [str(t).strip() for t in tags if str(t).strip()]
    if isinstance(tags, str):
        return [t.strip() for t in tags.split(",") if t.strip()]
    return [str(tags)]


def _load_markdown(dir_path: Path) -> List[Path]:
    if not dir_path.exists():
        return []
    return sorted([p for p in dir_path.glob("*.md") if p.name not in INDEX_FILES])


def load_values(dir_path: Path) -> List[Dict[str, Any]]:
    items = []
    for path in _load_markdown(dir_path):
        text = _read_text(path)
        frontmatter = _parse_frontmatter(text)
        tags = _as_list(frontmatter.get("tags"))
        if tags and "value" not in tags:
            continue
        inline = _parse_inline_fields(text)
        items.append(
            {
                "id": path.stem,
                "name": _extract_title(text, path.stem),
                "why": inline.get("why"),
            }
        )
    return items


def load_goals(dir_path: Path) -> List[Dict[str, Any]]:
    items = []
    for path in _load_markdown(dir_path):
        text = _read_text(path)
        frontmatter = _parse_frontmatter(text)
        tags = _as_list(frontmatter.get("tags"))
        if tags and "goal" not in tags:
            continue
        inline = _parse_inline_fields(text)
        value_name = _extract_link(inline.get("value"))
        items.append(
            {
                "id": path.stem,
                "name": _extract_title(text, path.stem),
                "status": frontmatter.get("status"),
                "why": inline.get("why"),
                "value": value_name,
                "deadline": _extract_date(inline.get("deadline")),
            }
        )
    return items


def load_projects(dir_path: Path) -> List[Dict[str, Any]]:
    items = []
    for path in _load_markdown(dir_path):
        text = _read_text(path)
        frontmatter = _parse_frontmatter(text)
        tags = _as_list(frontmatter.get("tags"))
        if tags and "project" not in tags:
            continue
        inline = _parse_inline_fields(text)
        goal_name = _extract_link(inline.get("goal"))
        items.append(
            {
                "id": path.stem,
                "name": _extract_title(text, path.stem),
                "status": frontmatter.get("status"),
                "goal": goal_name,
                "target": inline.get("target"),
                "deadline": _extract_date(inline.get("deadline")),
            }
        )
    return items


def _parse_date(date_str: Optional[str]) -> Optional[dt.date]:
    if not date_str:
        return None
    try:
        return dt.date.fromisoformat(date_str)
    except Exception:
        return None


def build_goal_graph() -> Dict[str, Any]:
    cfg = get_config()
    values_dir = Path(str(cfg.get("values_dir", ""))).expanduser()
    goals_dir = Path(str(cfg.get("goals_dir", ""))).expanduser()
    projects_dir = Path(str(cfg.get("projects_dir", ""))).expanduser()
    values = load_values(values_dir)
    goals = load_goals(goals_dir)
    projects = load_projects(projects_dir)

    value_map = {v["name"]: {**v, "goals": []} for v in values}
    goal_map: Dict[str, Dict[str, Any]] = {}
    for goal in goals:
        goal_copy = {**goal, "projects": []}
        goal_map[goal["name"]] = goal_copy
        value_name = goal.get("value")
        if value_name and value_name in value_map:
            value_map[value_name]["goals"].append(goal_copy)

    for project in projects:
        goal_name = project.get("goal")
        if goal_name and goal_name in goal_map:
            goal_map[goal_name]["projects"].append(project)

    graph = {
        "generated_at": dt.datetime.now().isoformat(),
        "values": list(value_map.values()),
        "goals": goals,
        "projects": projects,
    }
    return graph


def save_goal_graph(graph: Dict[str, Any], cache_path: Optional[Path] = None) -> Path:
    cfg = get_config()
    if cache_path is None:
        cache_root = Path(str(cfg.get("cache_root", ""))).expanduser()
        cache_path = cache_root / "goal_graph.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(graph, ensure_ascii=True, indent=2), encoding="utf-8")
    return cache_path
