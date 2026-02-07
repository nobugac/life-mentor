#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core import goal_manager, llm_analyzer, state_analytics, state_recorder
from integrations.config import get_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Debug morning prompt locally.")
    parser.add_argument("--date", type=str, help="Morning date (YYYY-MM-DD), default today")
    parser.add_argument("--state-date", type=str, help="State date override (YYYY-MM-DD)")
    parser.add_argument("--prompt", type=Path, help="Prompt file path override")
    parser.add_argument("--provider", type=str, help="Provider override")
    parser.add_argument("--model", type=str, help="Model override")
    parser.add_argument("--text", type=str, default="", help="早间文字输入")
    parser.add_argument("--print-prompt", action="store_true", help="Print rendered prompt to stdout")
    parser.add_argument("--output-dir", type=Path, help="LLM debug output dir override")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    date = dt.date.fromisoformat(args.date) if args.date else dt.date.today()
    if args.state_date:
        state_date = dt.date.fromisoformat(args.state_date)
    else:
        state_date = date - dt.timedelta(days=1)

    graph = goal_manager.build_goal_graph()
    goal_manager.save_goal_graph(graph)
    state = state_recorder.load_daily_state(state_date)
    trends = state_analytics.summarize_multi_windows(state_date)

    prompt_path = args.prompt
    cfg = get_config()
    output_dir = args.output_dir or Path(str(cfg.get("debug_llm_dir", ""))).expanduser()
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)

    text_input = args.text
    if not text_input:
        default_text_path = ROOT_DIR / "test_data" / "morning" / "text" / "input.txt"
        if default_text_path.exists():
            text_input = default_text_path.read_text(encoding="utf-8").rstrip("\n")
    if text_input is not None and not text_input.strip():
        text_input = None
    inputs = {"text": text_input}
    prompt_template = None
    if prompt_path:
        prompt_template = llm_analyzer._load_prompt(prompt_path)
    else:
        prompt_path = Path(str(cfg.get("morning_prompt_path", ""))).expanduser()
        prompt_template = llm_analyzer._load_prompt(prompt_path)

    if prompt_template:
        variables = {
            "date": date.isoformat(),
            "state_summary": llm_analyzer._json_dump(state or {}),
            "trend_summary": llm_analyzer._json_dump(trends),
            "goal_graph": llm_analyzer._json_dump(llm_analyzer._extract_goal_summary(graph)),
            "progress_summary": "",
            "user_input": llm_analyzer._json_dump(inputs),
        }
        rendered = llm_analyzer._render_template(prompt_template, variables)
        ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        if output_dir:
            prompt_out = output_dir / f"morning_prompt_{ts}.txt"
            prompt_out.write_text(rendered, encoding="utf-8")
            print(f"Rendered prompt saved: {prompt_out}")
        if args.print_prompt:
            print("----- PROMPT BEGIN -----")
            print(rendered)
            print("----- PROMPT END -----")

    result = llm_analyzer.generate_morning_llm(
        date,
        state,
        trends,
        graph,
        inputs,
        prompt_path_override=prompt_path if prompt_path else None,
        provider_override=args.provider,
        model_override=args.model,
        results_dir_override=output_dir if output_dir else None,
    )

    if not result:
        print("LLM result is empty (check prompt file or API).")
        return 1
    from pprint import pprint
    pprint(result)
    saved = result.get("saved")
    if saved:
        print(f"Saved: {saved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
