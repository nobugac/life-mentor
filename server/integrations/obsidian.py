from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from .config import get_config


@dataclass
class ObsidianPaths:
    vault_root: Path
    diary_day_root: Path
    backup_root: Path
    write_root: Path
    daily_template_path: Optional[Path] = None

    @classmethod
    def from_config(cls) -> "ObsidianPaths":
        cfg = get_config()
        vault_root = Path(str(cfg.get("vault_root", ""))).expanduser()
        diary_day_root = Path(str(cfg.get("diary_day_root", ""))).expanduser()
        backup_root = Path(str(cfg.get("backup_root", ""))).expanduser()
        write_root = Path(str(cfg.get("write_root", ""))).expanduser()
        tpl = cfg.get("daily_template_path")
        daily_template_path = Path(str(tpl)).expanduser() if tpl else None
        return cls(
            vault_root=vault_root,
            diary_day_root=diary_day_root,
            backup_root=backup_root,
            write_root=write_root,
            daily_template_path=daily_template_path,
        )


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def ensure_write_allowed(path: Path, write_root: Path) -> None:
    if not _is_relative_to(path, write_root):
        raise ValueError(f"Write blocked: {path} not under {write_root}")


def _backup_path_for(path: Path, backup_root: Path) -> Path:
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    name = path.name.replace(" ", "_")
    return backup_root / f"{ts}__{name}"


def safe_write_text(path: Path, text: str, backup_root: Path, write_root: Path) -> Optional[Path]:
    ensure_write_allowed(path, write_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = None
    if path.exists():
        current = path.read_text(encoding="utf-8")
        if current == text:
            return
        backup_root.mkdir(parents=True, exist_ok=True)
        backup_path = _backup_path_for(path, backup_root)
        backup_path.write_text(current, encoding="utf-8")
    path.write_text(text, encoding="utf-8")
    return backup_path


def replace_or_append_section(
    text: str, heading: str, new_body: str, heading_level: int = 2
) -> str:
    pattern = re.compile(
        rf"(^{ '#' * heading_level }\s+{re.escape(heading)}\s*\n)(.*?)(?=^#{{1,{heading_level}}}\s|\Z)",
        re.DOTALL | re.MULTILINE,
    )
    def _replace(match: re.Match) -> str:
        return f"{match.group(1)}{new_body.rstrip()}\n\n"

    if pattern.search(text):
        return pattern.sub(_replace, text)
    return text.rstrip() + f"\n\n{'#' * heading_level} {heading}\n{new_body.rstrip()}\n\n"


def update_subsection_in_section(
    text: str,
    section_heading: str,
    subsection_heading: str,
    new_body: str,
    section_level: int = 2,
    subsection_level: int = 3,
) -> str:
    section_pattern = re.compile(
        rf"(^{ '#' * section_level }\s+{re.escape(section_heading)}\s*\n)(.*?)(?=^#{{1,{section_level}}}\s|\Z)",
        re.DOTALL | re.MULTILINE,
    )

    def _replace(match: re.Match) -> str:
        header = match.group(1)
        body = match.group(2)
        updated_body = replace_or_append_section(
            body, subsection_heading, new_body, heading_level=subsection_level
        )
        return f"{header}{updated_body.rstrip()}\n\n"

    if section_pattern.search(text):
        return section_pattern.sub(_replace, text, count=1)

    section = (
        f"{'#' * section_level} {section_heading}\n\n"
        f"{'#' * subsection_level} {subsection_heading}\n"
        f"{new_body.rstrip()}\n\n"
    )
    return text.rstrip() + "\n\n" + section


def append_list_items(existing: str, items: Iterable[str]) -> str:
    lines = [line for line in existing.splitlines() if line.strip()]
    for item in items:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


FRONTMATTER_KEY_RE = re.compile(r"^([A-Za-z0-9_-]+)\s*:")


def _format_scalar(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if text.startswith("[[") and text.endswith("]]"):
        return text
    if any(ch in text for ch in [":", "#", "{", "}", "[", "]", ","]) or text.strip() != text:
        return '"' + text.replace('"', '\\"') + '"'
    return text


def _format_frontmatter_lines(key: str, value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items = [_format_scalar(v) for v in value if v not in (None, "")]
        if not items:
            return []
        lines = [f"{key}:"]
        for item in items:
            lines.append(f"  - {item}")
        return lines
    if isinstance(value, str) and not value.strip():
        return []
    return [f"{key}: {_format_scalar(value)}"]


def update_frontmatter(text: str, updates: dict) -> str:
    if not updates:
        return text
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        end = None
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end = i
                break
        if end is not None:
            fm_lines = lines[1:end]
            new_lines = []
            existing = set()
            i = 0
            while i < len(fm_lines):
                match = FRONTMATTER_KEY_RE.match(fm_lines[i].strip())
                if match:
                    key = match.group(1)
                    j = i + 1
                    while j < len(fm_lines) and not FRONTMATTER_KEY_RE.match(
                        fm_lines[j].strip()
                    ):
                        j += 1
                    if key in updates:
                        existing.add(key)
                        new_lines.extend(_format_frontmatter_lines(key, updates[key]))
                    else:
                        new_lines.extend(fm_lines[i:j])
                    i = j
                    continue
                new_lines.append(fm_lines[i])
                i += 1
            for key, value in updates.items():
                if key not in existing:
                    new_lines.extend(_format_frontmatter_lines(key, value))
            lines[1:end] = new_lines
            updated = "\n".join(lines)
            return updated + ("\n" if text.endswith("\n") else "")
    fm_lines = ["---"]
    for key, value in updates.items():
        fm_lines.extend(_format_frontmatter_lines(key, value))
    fm_lines.append("---")
    updated = "\n".join(fm_lines + lines)
    return updated + ("\n" if text.endswith("\n") else "")


def _render_daily_template(template_text: str, date: dt.date) -> str:
    iso = date.isocalendar()
    week = iso.week if hasattr(iso, "week") else iso[1]
    week_id = f"{date.strftime('%Y')}-W{week}"
    replacements = {
        '<% tp.date.now("YYYY-MM-DD") %>': date.isoformat(),
        '<% tp.date.now("YYYY-MM") %>': date.strftime("%Y-%m"),
        '<% tp.file.title %>': date.isoformat(),
        '<% tp.file.title.slice(0, 7) %>': date.strftime("%Y-%m"),
        '<% tp.date.now("YYYY", 0, tp.file.title, "YYYY-MM-DD") %>': date.strftime("%Y"),
        '<% tp.date.now("W", 0, tp.file.title, "YYYY-MM-DD") %>': f"{week}",
        '<% tp.date.now("YYYY-[W]WW", 0, tp.file.title, "YYYY-MM-DD") %>': week_id,
        '<% tp.date.now("YYYY-[W]W", 0, tp.file.title, "YYYY-MM-DD") %>': week_id,
        '<% tp.date.now("YYYY-[W]WW") %>': week_id,
        '<% tp.date.now("YYYY-[W]W") %>': week_id,
        '<% tp.date.now("YYYY-MM", 0, tp.file.title, "YYYY-[W]WW") %>': date.strftime("%Y-%m"),
        '<% tp.date.now("YYYY-MM", 0, tp.file.title, "YYYY-[W]W") %>': date.strftime("%Y-%m"),
    }
    rendered = template_text
    for token, value in replacements.items():
        rendered = rendered.replace(token, value)
    return rendered


def render_template(template_text: str, date: dt.date) -> str:
    return _render_daily_template(template_text, date)


def ensure_daily_file(date: dt.date, paths: Optional[ObsidianPaths] = None) -> Path:
    obsidian_paths = paths or ObsidianPaths.from_config()
    diary_root = obsidian_paths.diary_day_root
    diary_root.mkdir(parents=True, exist_ok=True)
    path = diary_root / f"{date.isoformat()}.md"
    if path.exists():
        return path
    template_text = None
    if obsidian_paths.daily_template_path and obsidian_paths.daily_template_path.exists():
        template_text = obsidian_paths.daily_template_path.read_text(encoding="utf-8")
        template_text = _render_daily_template(template_text, date)
    if template_text is None:
        template_text = (
            "---\n"
            f"journal: day\njournal-date: {date.isoformat()}\n"
            "---\n\n"
            "# 记录\n"
        )
    safe_write_text(path, template_text, obsidian_paths.backup_root, obsidian_paths.write_root)
    return path
