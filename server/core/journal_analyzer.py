from __future__ import annotations

from typing import Any, Dict, List, Optional


MOOD_KEYWORDS = {
    "积极": ["开心", "高兴", "满足", "轻松", "愉快", "顺利"],
    "疲惫": ["累", "疲", "困", "倦", "乏力"],
    "焦虑": ["焦虑", "压力", "烦", "紧张", "担心"],
    "低落": ["难过", "沮丧", "失落", "不开心"],
}

TOPIC_KEYWORDS = {
    "健康": ["睡", "睡眠", "运动", "健身", "跑步", "饮食", "体重"],
    "工作": ["工作", "项目", "会议", "同事", "老板", "客户"],
    "学习": ["学习", "读书", "课程", "知识", "笔记", "研究"],
    "投资": ["投资", "理财", "股票", "基金", "收益", "仓位"],
    "家庭": ["家人", "父母", "孩子", "伴侣", "家庭"],
    "生活": ["整理", "家务", "买菜", "做饭", "出行"],
}


def _summarize(text: str, max_len: int = 120) -> str:
    cleaned = " ".join([line.strip() for line in text.splitlines() if line.strip()])
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[:max_len].rstrip() + "..."


def _detect_mood(text: str) -> Optional[str]:
    for mood, keywords in MOOD_KEYWORDS.items():
        if any(k in text for k in keywords):
            return mood
    return None


def _detect_topics(text: str) -> List[str]:
    topics = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(k in text for k in keywords):
            topics.append(topic)
    return topics


def _detect_linked_projects(text: str, projects: List[Dict[str, Any]]) -> List[str]:
    linked = []
    for project in projects:
        name = project.get("name")
        if name and name in text:
            linked.append(f"[[{name}]]")
    return linked


def analyze_journal(
    journal_text: str,
    graph: Optional[Dict[str, Any]] = None,
    extra_texts: Optional[List[str]] = None,
) -> Dict[str, Any]:
    text = journal_text.strip()
    combined = text
    if extra_texts:
        combined = combined + "\n" + "\n".join([t for t in extra_texts if t])
    projects = (graph or {}).get("projects") or []
    mood = _detect_mood(combined)
    topics = _detect_topics(combined)
    linked_projects = _detect_linked_projects(combined, projects)
    return {
        "summary": _summarize(text),
        "mood": mood,
        "topics": topics,
        "linked_projects": linked_projects,
    }


def format_evening_summary(
    journal_text: str,
    analysis: Dict[str, Any],
    records: Optional[List[str]] = None,
    reflection: Optional[str] = None,
) -> str:
    lines: List[str] = []
    summary = analysis.get("summary")
    if summary:
        lines.append(f"- 摘要：{summary}")
    mood = analysis.get("mood")
    if mood:
        lines.append(f"- 情绪：{mood}")
    topics = analysis.get("topics") or []
    if topics:
        lines.append(f"- 主题：{', '.join(topics)}")
    linked = analysis.get("linked_projects") or []
    if linked:
        lines.append(f"- 关联项目：{', '.join(linked)}")
    if reflection:
        lines.append(f"- 反思：{reflection}")
    lines.append("- 原文：")
    for line in journal_text.splitlines():
        content = line.strip()
        if content:
            lines.append(f"  - {content}")
    if records:
        lines.append("- 临时记录：")
        for item in records:
            item_text = item.strip()
            if item_text:
                lines.append(f"  - {item_text}")
    return "\n".join(lines) + "\n"
