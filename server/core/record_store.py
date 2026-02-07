from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Dict, List, Optional

from integrations.config import get_config


def _records_root() -> Path:
    cfg = get_config()
    root = Path(str(cfg.get("records_root", ""))).expanduser()
    if not root:
        raise ValueError("records_root is not configured")
    root.mkdir(parents=True, exist_ok=True)
    return root


def add_record(date: dt.date, text: str, source: str = "manual") -> Path:
    payload = {
        "timestamp": dt.datetime.now().isoformat(),
        "date": date.isoformat(),
        "source": source,
        "text": text,
    }
    path = _records_root() / f"{date.isoformat()}.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
    return path


def load_records(date: dt.date) -> List[Dict[str, str]]:
    path = _records_root() / f"{date.isoformat()}.jsonl"
    if not path.exists():
        return []
    records: List[Dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        text = data.get("text")
        if text:
            records.append(data)
    return records


def summarize_records(records: List[Dict[str, str]]) -> List[str]:
    items = []
    for record in records:
        text = record.get("text")
        if text:
            items.append(text)
    return items
