from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_config_path() -> Path:
    return _repo_root() / "config" / "config.yaml"


def _coerce_value(raw: str):
    lowered = raw.strip().lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none", "~"}:
        return None
    return raw


def _parse_simple_yaml(text: str) -> Dict[str, object]:
    data: Dict[str, object] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value.startswith(("'", '"')) and value.endswith(("'", '"')):
            value = value[1:-1]
        data[key] = _coerce_value(value)
    return data


def load_config(path: Optional[Path] = None) -> Dict[str, object]:
    cfg_path = path or Path(os.environ.get("LIFE_MENTOR_CONFIG", "")).expanduser()
    if not cfg_path or str(cfg_path) == ".":
        cfg_path = _default_config_path()
    if not cfg_path.exists():
        raise FileNotFoundError(f"Config not found: {cfg_path}")
    text = cfg_path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text) or {}
        if not isinstance(data, dict):
            raise ValueError("config.yaml must be a mapping at top level")
        return data
    except Exception:
        return _parse_simple_yaml(text)


_CACHED: Optional[Dict[str, object]] = None


def get_config(path: Optional[Path] = None) -> Dict[str, object]:
    global _CACHED
    if _CACHED is None or path is not None:
        _CACHED = load_config(path)
    return _CACHED
