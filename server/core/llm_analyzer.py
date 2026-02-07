from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from integrations.config import get_config
from integrations import llm_client


def _load_prompt(path: Path) -> Optional[str]:
    if path and path.exists():
        return path.read_text(encoding="utf-8")
    return None


def _render_template(template: str, variables: Dict[str, str]) -> str:
    rendered = template
    for key, value in variables.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return rendered


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _llm_results_dir() -> Path:
    cfg = get_config()
    root = Path(str(cfg.get("llm_results_dir", ""))).expanduser()
    if not root:
        raise ValueError("llm_results_dir is not configured")
    root.mkdir(parents=True, exist_ok=True)
    return root


def _save_llm_result(kind: str, payload: Dict[str, Any], root_override: Optional[Path] = None) -> Path:
    root = root_override or _llm_results_dir()
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = root / f"{kind}_{ts}.json"
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    return path


def _extract_usage(resp: Any) -> Optional[Dict[str, int]]:
    usage = getattr(resp, "usage", None)
    if not usage:
        return None
    data: Dict[str, Any] = {}
    if isinstance(usage, dict):
        data = usage
    else:
        for attr in ("prompt_tokens", "completion_tokens", "total_tokens", "input_tokens", "output_tokens"):
            if hasattr(usage, attr):
                data[attr] = getattr(usage, attr)
        if hasattr(usage, "model_dump"):
            try:
                data.update(usage.model_dump())  # type: ignore[arg-type]
            except Exception:
                pass
        elif hasattr(usage, "dict"):
            try:
                data.update(usage.dict())  # type: ignore[arg-type]
            except Exception:
                pass

    input_tokens = data.get("prompt_tokens")
    if input_tokens is None:
        input_tokens = data.get("input_tokens")
    output_tokens = data.get("completion_tokens")
    if output_tokens is None:
        output_tokens = data.get("output_tokens")
    total_tokens = data.get("total_tokens")
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens

    if input_tokens is None and output_tokens is None and total_tokens is None:
        return None
    result: Dict[str, int] = {}
    if input_tokens is not None:
        result["input_tokens"] = int(input_tokens)
    if output_tokens is not None:
        result["output_tokens"] = int(output_tokens)
    if total_tokens is not None:
        result["total_tokens"] = int(total_tokens)
    return result or None


def _log_llm_usage(kind: str, provider: str, model: str, usage: Optional[Dict[str, int]]) -> None:
    if not usage:
        return
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    total_tokens = usage.get("total_tokens")
    print(
        f"[LLM] {kind} provider={provider} model={model} "
        f"input={input_tokens} output={output_tokens} total={total_tokens}"
    )


def _call_llm_json(provider: str, model: str, prompt: str) -> Tuple[Dict[str, Any], Optional[Dict[str, int]]]:
    cfg = get_config()
    timeout_seconds = None
    timeout_raw = cfg.get("llm_timeout_seconds")
    if timeout_raw is not None:
        try:
            timeout_seconds = float(timeout_raw)
        except (TypeError, ValueError):
            timeout_seconds = None
    client = llm_client.make_client(provider, timeout_seconds=timeout_seconds)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    usage = _extract_usage(resp)
    content = resp.choices[0].message.content  # type: ignore
    return json.loads(content), usage


def _extract_goal_summary(graph: Dict[str, Any]) -> Dict[str, Any]:
    goals = graph.get("goals") or []
    projects = graph.get("projects") or []
    values = graph.get("values") or []
    value_summaries = []
    for value in values:
        goals_in_value = value.get("goals") or []
        value_summaries.append(
            {
                "name": value.get("name"),
                "why": value.get("why"),
                "goals": [
                    {
                        "name": g.get("name"),
                        "status": g.get("status"),
                        "deadline": g.get("deadline"),
                        "projects": [
                            {
                                "name": p.get("name"),
                                "status": p.get("status"),
                                "deadline": p.get("deadline"),
                                "target": p.get("target"),
                            }
                            for p in (g.get("projects") or [])
                        ],
                    }
                    for g in goals_in_value
                ],
            }
        )
    return {
        "values": value_summaries,
        "goals": [
            {
                "name": g.get("name"),
                "status": g.get("status"),
                "deadline": g.get("deadline"),
                "value": g.get("value"),
            }
            for g in goals
        ],
        "projects": [
            {
                "name": p.get("name"),
                "status": p.get("status"),
                "deadline": p.get("deadline"),
                "goal": p.get("goal"),
                "target": p.get("target"),
            }
            for p in projects
        ],
    }


def generate_morning_llm(
    date: dt.date,
    state: Optional[Dict[str, Any]],
    trends: List[Dict[str, Any]],
    goal_graph: Dict[str, Any],
    inputs: Dict[str, Optional[str]],
    prompt_path_override: Optional[Path] = None,
    provider_override: Optional[str] = None,
    model_override: Optional[str] = None,
    results_dir_override: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    cfg = get_config()
    prompt_path = prompt_path_override or Path(str(cfg.get("morning_prompt_path", ""))).expanduser()
    prompt_template = _load_prompt(prompt_path)
    if not prompt_template:
        return None
    provider = provider_override or str(cfg.get("morning_provider", "doubao"))
    model = model_override or str(cfg.get("morning_model", "doubao-seed-1-6-251015"))

    active_goals = []
    raw_active_goals = inputs.get("active_goals") if isinstance(inputs, dict) else None
    if isinstance(raw_active_goals, list):
        active_goals = [str(item) for item in raw_active_goals if item]

    variables = {
        "date": date.isoformat(),
        "state_summary": _json_dump(state or {}),
        "trend_summary": _json_dump(trends),
        "goal_graph": _json_dump(_extract_goal_summary(goal_graph)),
        "active_goals": _json_dump(active_goals),
        "progress_summary": "",
        "user_input": _json_dump(inputs),
    }
    prompt = _render_template(prompt_template, variables)
    payload = {
        "type": "morning",
        "provider": provider,
        "model": model,
        "prompt_path": str(prompt_path),
        "prompt_version": prompt_path.stem if prompt_path else None,
        "prompt_source": "override" if prompt_path_override else "config",
        "inputs": {**inputs, "date": date.isoformat()},
        "context": {
            "state": state,
            "trends": trends,
            "goal_graph_summary": _extract_goal_summary(goal_graph),
            "active_goals": active_goals,
        },
    }
    try:
        result, usage = _call_llm_json(provider, model, prompt)
    except Exception as exc:
        payload["error"] = str(exc)
        _save_llm_result("morning_error", payload, root_override=results_dir_override)
        return None
    if usage:
        payload["usage"] = usage
        _log_llm_usage("morning", provider, model, usage)
    payload["raw_result"] = result
    saved = _save_llm_result("morning", payload, root_override=results_dir_override)
    result["saved"] = str(saved)
    return result


def generate_evening_llm(
    date: dt.date,
    journal_text: str,
    records: List[str],
    goal_graph: Dict[str, Any],
    prompt_path_override: Optional[Path] = None,
    provider_override: Optional[str] = None,
    model_override: Optional[str] = None,
    results_dir_override: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    cfg = get_config()
    prompt_path = prompt_path_override or Path(str(cfg.get("evening_prompt_path", ""))).expanduser()
    prompt_template = _load_prompt(prompt_path)
    if not prompt_template:
        return None
    provider = provider_override or str(cfg.get("evening_provider", "doubao"))
    model = model_override or str(cfg.get("evening_model", "doubao-seed-1-6-251015"))

    is_sunday = date.weekday() == 6
    _is_en = "_en" in (prompt_path.name if prompt_path else "")
    if _is_en:
        weekday_label = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][date.weekday()]
        is_sunday_str = "yes" if is_sunday else "no"
    else:
        weekday_label = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][date.weekday()]
        is_sunday_str = "是" if is_sunday else "否"
    variables = {
        "date": date.isoformat(),
        "weekday": weekday_label,
        "is_sunday": is_sunday_str,
        "journal_text": journal_text,
        "records": _json_dump(records),
        "goal_graph": _json_dump(_extract_goal_summary(goal_graph)),
    }
    prompt = _render_template(prompt_template, variables)
    payload = {
        "type": "evening",
        "provider": provider,
        "model": model,
        "prompt_path": str(prompt_path),
        "prompt_version": prompt_path.stem if prompt_path else None,
        "prompt_source": "override" if prompt_path_override else "config",
        "inputs": {
            "date": date.isoformat(),
            "weekday": weekday_label,
            "is_sunday": is_sunday,
            "journal_text": journal_text,
            "records": records,
        },
        "context": {"goal_graph_summary": _extract_goal_summary(goal_graph)},
    }
    try:
        result, usage = _call_llm_json(provider, model, prompt)
    except Exception as exc:
        payload["error"] = str(exc)
        _save_llm_result("evening_error", payload, root_override=results_dir_override)
        return None
    if usage:
        payload["usage"] = usage
        _log_llm_usage("evening", provider, model, usage)
    payload["raw_result"] = result
    saved = _save_llm_result("evening", payload, root_override=results_dir_override)
    result["saved"] = str(saved)
    return result


def generate_alignment_llm(
    date: dt.date,
    state: Optional[Dict[str, Any]],
    trends: List[Dict[str, Any]],
    goal_graph: Dict[str, Any],
    active_goals: List[str],
    records: Optional[List[str]] = None,
    prompt_path_override: Optional[Path] = None,
    provider_override: Optional[str] = None,
    model_override: Optional[str] = None,
    results_dir_override: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    cfg = get_config()
    prompt_path = prompt_path_override or Path(str(cfg.get("alignment_prompt_path", ""))).expanduser()
    prompt_template = _load_prompt(prompt_path)
    if not prompt_template:
        return None
    provider = provider_override or str(cfg.get("alignment_provider", "doubao"))
    model = model_override or str(cfg.get("alignment_model", "doubao-seed-1-6-251015"))

    variables = {
        "date": date.isoformat(),
        "state_summary": _json_dump(state or {}),
        "trend_summary": _json_dump(trends),
        "recent_records": _json_dump(records or []),
        "goal_graph": _json_dump(_extract_goal_summary(goal_graph)),
        "active_goals": _json_dump(active_goals),
    }
    prompt = _render_template(prompt_template, variables)
    payload = {
        "type": "alignment",
        "provider": provider,
        "model": model,
        "prompt_path": str(prompt_path),
        "prompt_version": prompt_path.stem if prompt_path else None,
        "prompt_source": "override" if prompt_path_override else "config",
        "inputs": {
            "date": date.isoformat(),
            "active_goals": active_goals,
            "records": records or [],
        },
        "context": {
            "state": state,
            "trends": trends,
            "goal_graph_summary": _extract_goal_summary(goal_graph),
            "active_goals": active_goals,
            "records": records or [],
        },
    }
    try:
        result, usage = _call_llm_json(provider, model, prompt)
    except Exception as exc:
        payload["error"] = str(exc)
        _save_llm_result("alignment_error", payload, root_override=results_dir_override)
        return None
    if usage:
        payload["usage"] = usage
        _log_llm_usage("alignment", provider, model, usage)
    payload["raw_result"] = result
    saved = _save_llm_result("alignment", payload, root_override=results_dir_override)
    result["saved"] = str(saved)
    return result
