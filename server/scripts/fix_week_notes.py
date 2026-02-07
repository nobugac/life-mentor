#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from integrations.config import get_config  # noqa: E402
from integrations.obsidian import render_template, safe_write_text  # noqa: E402


WEEK_RE = re.compile(r"^(?P<year>\d{4})-W(?P<week>\d{1,2})$")
PADDED_WEEK_RE = re.compile(r"^(?P<year>\d{4})-W0(?P<week>\d{1,2})$")


def _parse_week_id(stem: str) -> Optional[Tuple[int, int]]:
    match = WEEK_RE.match(stem)
    if match:
        return int(match.group("year")), int(match.group("week"))
    match = PADDED_WEEK_RE.match(stem)
    if match:
        return int(match.group("year")), int(match.group("week"))
    return None


def _normalize_week_id(year: int, week: int) -> str:
    return f"{year}-W{week}"


def _canonical_map(paths: List[Path]) -> Dict[str, Dict[str, Union[List[Path], Path, None]]]:
    mapping: Dict[str, Dict[str, Union[List[Path], Path, None]]] = {}
    for path in paths:
        parsed = _parse_week_id(path.stem)
        if not parsed:
            continue
        year, week = parsed
        week_id = _normalize_week_id(year, week)
        entry = mapping.setdefault(week_id, {"canonical": None, "duplicates": []})
        canonical = entry["canonical"]
        if path.stem == week_id:
            if canonical and isinstance(canonical, Path) and canonical != path:
                entry["duplicates"].append(canonical)
            entry["canonical"] = path
        else:
            if canonical is None:
                entry["canonical"] = path
            else:
                entry["duplicates"].append(path)
    return mapping


def _update_frontmatter_week(text: str, week_id: str) -> str:
    updated = re.sub(r"^week:\s*.*$", f"week: {week_id}", text, flags=re.MULTILINE)
    updated = re.sub(
        r"^journal-week:\s*.*$", f"journal-week: {week_id}", updated, flags=re.MULTILINE
    )
    return updated


def _iso_week_start(year: int, week: int) -> dt.date:
    if hasattr(dt.date, "fromisocalendar"):
        return dt.date.fromisocalendar(year, week, 1)
    jan4 = dt.date(year, 1, 4)
    week1_start = jan4 - dt.timedelta(days=jan4.isoweekday() - 1)
    return week1_start + dt.timedelta(weeks=week - 1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize weekly note names and tokens.")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default: dry run)")
    args = parser.parse_args()

    cfg = get_config()
    week_root_value = cfg.get("diary_week_root")
    if not week_root_value:
        raise RuntimeError("Missing config: diary_week_root")
    week_root = Path(str(week_root_value)).expanduser()
    backup_root = Path(str(cfg.get("backup_root", ""))).expanduser()
    write_root = Path(str(cfg.get("week_write_root", week_root))).expanduser()

    paths = sorted(week_root.glob("*.md"))
    mapping = _canonical_map(paths)
    if not mapping:
        print("No weekly notes found.")
        return 0

    total_updates = 0
    total_renames = 0
    for week_id, entry in mapping.items():
        canonical = entry["canonical"]
        if not isinstance(canonical, Path):
            continue
        if entry["duplicates"]:
            dup_names = ", ".join(p.name for p in entry["duplicates"])
            print(f"[warn] duplicate week notes for {week_id}: {dup_names}")

        desired_path = canonical.with_name(f"{week_id}.md")
        rename_needed = canonical != desired_path
        if rename_needed and desired_path.exists() and desired_path != canonical:
            print(f"[skip] {canonical.name} -> {desired_path.name} (target exists)")
            rename_needed = False

        parsed = _parse_week_id(week_id)
        if not parsed:
            continue
        year, week = parsed
        week_date = _iso_week_start(year, week)

        text = canonical.read_text(encoding="utf-8")
        rendered = render_template(text, week_date)
        rendered = _update_frontmatter_week(rendered, week_id)

        if rename_needed:
            print(f"[rename] {canonical.name} -> {desired_path.name}")
            if args.apply:
                canonical.rename(desired_path)
                canonical = desired_path
            total_renames += 1

        if rendered != text:
            print(f"[update] {canonical.name}")
            if args.apply:
                safe_write_text(canonical, rendered, backup_root, write_root)
            total_updates += 1

    if not args.apply:
        print("Dry run complete. Use --apply to write changes.")
    print(f"Renames: {total_renames}, Updates: {total_updates}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
