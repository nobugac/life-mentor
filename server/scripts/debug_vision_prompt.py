#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import sys
from pathlib import Path
from typing import List, Optional

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import chat_bot
from core import state_recorder
from integrations.config import get_config
from integrations import llm_client


def _load_prompt(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _data_urls_from_files(paths: List[Path]) -> List[str]:
    urls = []
    for path in paths:
        data = path.read_bytes()
        b64 = base64.b64encode(data).decode("ascii")
        urls.append(f"data:image/jpeg;base64,{b64}")
    return urls


def _save_vision_result(
    provider: str,
    model: str,
    capture_date: dt.date,
    prompt: str,
    prompt_path: Optional[Path],
    result_text: str,
    images: List[str],
    result_dir: Path,
) -> Path:
    result_dir.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_model = model.replace("/", "_")
    path = result_dir / f"vision_{ts}_{provider}_{safe_model}.json"
    payload = {
        "provider": provider,
        "model": model,
        "timestamp": ts,
        "capture_date": capture_date.isoformat(),
        "prompt": prompt,
        "prompt_path": str(prompt_path) if prompt_path else None,
        "prompt_version": prompt_path.stem if prompt_path else None,
        "prompt_source": "override" if prompt_path else "config",
        "images": images,
        "result": None,
        "raw": result_text,
    }
    try:
        payload["result"] = json.loads(result_text)
    except Exception:
        payload["result"] = None
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    return path


def _save_debug_state(state: dict, state_dir: Path) -> Path:
    state_dir.mkdir(parents=True, exist_ok=True)
    date_str = state.get("date")
    if not date_str:
        raise ValueError("state.date is required")
    path = state_dir / f"{date_str}.json"
    path.write_text(json.dumps(state, ensure_ascii=True, indent=2), encoding="utf-8")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Debug vision prompt with local images.")
    parser.add_argument("--images", type=Path, nargs="+", required=True, help="Image file paths")
    parser.add_argument("--date", type=str, help="Capture date (YYYY-MM-DD), default yesterday")
    parser.add_argument(
        "--provider",
        type=str,
        default="doubao",
        choices=["doubao", "openai", "openrouter"],
        help="Provider name",
    )
    parser.add_argument("--model", type=str, default=chat_bot.DEFAULT_VISION_MODEL, help="Vision model")
    parser.add_argument("--prompt", type=Path, help="Prompt file path override")
    parser.add_argument("--update-state", action="store_true", help="Save normalized state JSON")
    parser.add_argument("--output-dir", type=Path, help="Vision debug output dir override")
    parser.add_argument("--state-dir", type=Path, help="Debug state output dir override")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    capture_date = dt.date.fromisoformat(args.date) if args.date else dt.date.today() - dt.timedelta(days=1)
    images = [p for p in args.images if p.exists()]
    if not images:
        raise SystemExit("No valid image paths provided.")

    cfg = get_config()
    prompt_path = args.prompt or Path(str(cfg.get("vision_prompt_path", ""))).expanduser()
    prompt = _load_prompt(prompt_path) if prompt_path and prompt_path.exists() else ""

    client = llm_client.make_client(args.provider)
    data_urls = _data_urls_from_files(images)
    result_text = chat_bot.vision_describe_multi(client, args.model, data_urls, prompt)

    result_dir = args.output_dir or Path(str(cfg.get("debug_vision_results_dir", ""))).expanduser()
    if not result_dir:
        raise SystemExit("debug_vision_results_dir is not configured")

    saved = _save_vision_result(
        provider=args.provider,
        model=args.model,
        capture_date=capture_date,
        prompt=prompt,
        prompt_path=prompt_path if prompt_path and prompt_path.exists() else None,
        result_text=result_text,
        images=data_urls,
        result_dir=result_dir,
    )
    print(f"Saved vision result: {saved}")

    if args.update_state:
        result_data = json.loads(result_text)
        state = state_recorder.build_daily_state(capture_date, vision_result=result_data)
        state_dir = args.state_dir or Path(str(cfg.get("debug_state_dir", ""))).expanduser()
        if not state_dir:
            raise SystemExit("debug_state_dir is not configured")
        state_path = _save_debug_state(state, state_dir)
        print(f"Saved state: {state_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
