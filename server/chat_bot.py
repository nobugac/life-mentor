#!/usr/bin/env python3
"""Chat-triggered daily helper using LLM classification + optional vision.

Workflow:
- User说话 -> LLM 解析意图（早/晚流程、文字输入、日记、图片路径）。
- 根据解析结果调用 manage_day 的早/晚更新函数，写入 Obsidian 日记。
- 可选：通过 vision 模型描述图片（Ark 示例）。

准备：
1) pip install openai
2) export OPENAI_API_KEY="sk-..." 或 ARK_API_KEY="..."（看你选择的 provider）
3) 可选：用 --goal-file 提供你的目标文本，作为 GPT 提示。

提示：本脚本不调用 GPT 写入日记正文，只用于意图解析；你可以在解析后把 user 消息直接写入日记。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import manage_day
from integrations import llm_client

DEFAULT_MODEL = "gpt-5-mini"
# Ark 默认模型：文本/图文多模态（支持 image_url），按你的示例改为最新 ID
DEFAULT_ARK_MODEL = "doubao-seed-1-6-flash-250828"
# 视觉模型（如需与上面统一，也可直接使用 DEFAULT_ARK_MODEL）
DEFAULT_VISION_MODEL = "doubao-seed-1-6-vision-250815"


def read_goal_text(goal_file: Optional[Path]) -> Optional[str]:
    if goal_file and goal_file.exists():
        return goal_file.read_text(encoding="utf-8")
    return None


def _normalize_provider(provider: str) -> str:
    if provider == "ark":
        return "doubao"
    return provider


def make_client(provider: str) -> Any:
    return llm_client.make_client(_normalize_provider(provider))


def classify_message(client: Any, model: str, user_text: str, goal_text: Optional[str]) -> Dict[str, Any]:
    """Ask LLM to produce a JSON plan."""
    system_prompt = (
        "你是 LifeMentor，一个温和的生活教练。输出 JSON，不要多余文本。"
        "字段: action: morning|evening|none; text: string|null; "
        "journal: string|null; images: array of file paths (strings); "
        "reply: string (必填，对用户的回复，温和、有洞察、简短)。"
        "如果用户没有提供 text/journal/images，填 null/[]。"
        "仅当用户明确早上开始、安排今天、生成待办时，用 morning。"
        "仅当用户说今晚、总结、记录日记时，用 evening。"
        "无法判断则 action 用 none。"
        "reply 始终要有内容，回复语言与用户输入一致（用户说英文就回英文，说中文就回中文）。"
    )
    goal_hint = f"目标提示: {goal_text[:800]}" if goal_text else "无目标提示"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"{goal_hint}\n用户: {user_text}"},
    ]
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0,
    )
    content = resp.choices[0].message.content  # type: ignore
    return json.loads(content)


def vision_describe(
    client: Any, model: str, image_url: str, prompt: str, reasoning_effort: str = "medium"
) -> str:
    """Use a vision model (e.g., Ark Doubao) to describe an image URL."""
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        reasoning_effort=reasoning_effort,
    )
    return resp.choices[0].message.content  # type: ignore


def vision_describe_base64(
    client: Any, model: str, image_b64: str, prompt: str, reasoning_effort: str = "medium"
) -> str:
    """Use a vision model with a base64 data URL."""
    data_url = f"data:image/jpeg;base64,{image_b64}"
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        reasoning_effort=reasoning_effort,
    )
    return resp.choices[0].message.content  # type: ignore


def vision_describe_multi(
    client: Any, model: str, image_urls: List[str], prompt: str, reasoning_effort: str = "medium"
) -> str:
    """Use a vision model with multiple image URLs or data URLs."""
    content = [{"type": "image_url", "image_url": {"url": url}} for url in image_urls]
    content.append({"type": "text", "text": prompt})
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": content}],
        reasoning_effort=reasoning_effort,
    )
    return resp.choices[0].message.content  # type: ignore


def apply_action(
    action: str,
    date: dt.date,
    goal_text: Optional[str],
    text_input: Optional[str],
    journal: Optional[str],
    images: List[str],
) -> Path:
    daily_path = manage_day.ensure_daily_file(date)
    img_paths = [Path(p) for p in images]
    if action == "morning":
        manage_day.run_morning(daily_path, goal_text, img_paths, text_input=text_input)
    elif action == "evening":
        manage_day.run_evening(daily_path, journal)
    return daily_path


def handle_single_turn(args: argparse.Namespace) -> None:
    client = make_client(args.provider)
    goal_text = read_goal_text(args.goal_file)
    result = classify_message(client, args.model, args.message, goal_text)
    action = result.get("action", "none")
    images = result.get("images", []) or []
    text_input = result.get("text")
    journal = result.get("journal")

    path = apply_action(action, args.date, goal_text, text_input, journal, images)
    output = {"action": action, "file": str(path), "parsed": result}

    # Optional vision call if user supplied --vision-url
    if args.vision_url:
        try:
            vision_text = vision_describe(client, args.vision_model, args.vision_url, args.vision_prompt)
            output["vision"] = vision_text
        except Exception as exc:  # pragma: no cover - network errors
            output["vision_error"] = str(exc)

    print(json.dumps(output, ensure_ascii=False, indent=2))


def handle_interactive(args: argparse.Namespace) -> None:
    client = make_client(args.provider)
    goal_text = read_goal_text(args.goal_file)
    print("进入对话模式，输入 'exit' 退出。")
    while True:
        user_text = input("> ").strip()
        if user_text.lower() in {"exit", "quit"}:
            break
        result = classify_message(client, args.model, user_text, goal_text)
        action = result.get("action", "none")
        images = result.get("images", []) or []
        text_input = result.get("text")
        journal = result.get("journal")
        path = apply_action(action, args.date, goal_text, text_input, journal, images)
        print(json.dumps({"action": action, "file": str(path), "parsed": result}, ensure_ascii=False, indent=2))


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chat-triggered daily note helper.")
    parser.add_argument("--date", type=lambda s: dt.date.fromisoformat(s), default=dt.date.today())
    parser.add_argument("--goal-file", type=Path, help="可选：目标文本文件，用于提示 GPT")
    parser.add_argument("--message", type=str, help="单轮消息；不提供则进入交互模式")
    parser.add_argument(
        "--provider",
        type=str,
        default="openai",
        choices=["openai", "ark", "doubao", "openrouter"],
        help="选择 API 提供方",
    )
    parser.add_argument("--model", type=str, help="聊天模型名称（默认 openai:gpt-5-mini / ark:doubao-pro-1.5）")
    parser.add_argument("--vision-url", type=str, help="可选：图片 URL，调用视觉模型描述")
    parser.add_argument("--vision-prompt", type=str, default="请简要描述图片关键信息", help="视觉模型提示语")
    parser.add_argument("--vision-model", type=str, default=DEFAULT_VISION_MODEL, help="视觉模型名称（默认 Ark 示例）")
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    if not args.model:
        args.model = DEFAULT_ARK_MODEL if args.provider in {"ark", "doubao"} else DEFAULT_MODEL
    if args.message:
        handle_single_turn(args)
    else:
        handle_interactive(args)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
