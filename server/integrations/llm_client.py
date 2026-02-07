from __future__ import annotations

import os
from typing import Any

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore


PROVIDERS = {
    "doubao": {
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "api_key_env": "ARK_API_KEY",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "api_key_env": "GEMINI_API_KEY",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
    },
    "openai": {
        "base_url": None,
        "api_key_env": "OPENAI_API_KEY",
    },
}


def make_client(
    provider: str,
    timeout_seconds: float | None = None,
    max_retries: int | None = None,
) -> Any:
    if OpenAI is None:
        raise RuntimeError("Missing dependency: pip install openai")
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider}")
    info = PROVIDERS[provider]
    api_key = os.getenv(info["api_key_env"])
    if not api_key:
        raise RuntimeError(f"Missing env {info['api_key_env']}")
    client_kwargs: dict[str, Any] = {}
    if timeout_seconds is not None:
        client_kwargs["timeout"] = timeout_seconds
    if max_retries is not None:
        client_kwargs["max_retries"] = max_retries
    base_url = info["base_url"]
    if base_url:
        return OpenAI(base_url=base_url, api_key=api_key, **client_kwargs)
    return OpenAI(api_key=api_key, **client_kwargs)
