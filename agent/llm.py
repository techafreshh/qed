"""Single Meta Model API client with deterministic offline stub (issue #7)."""

import os

from app.config import parse_offline

API_URL = "https://api.llama.com/v1/chat/completions"
MODEL = "Llama-4-Maverick-17B-128E-Instruct-FP8"
DEFAULT_MAX_TOKENS = 256
MAX_TOKENS_CAP = 512
TIMEOUT = 10.0


def _stub(prompt: str) -> str:
    return f"stub:{prompt.strip()[:64] or 'empty'}"


def complete(prompt: str, max_tokens: int = DEFAULT_MAX_TOKENS) -> str:
    """Complete a prompt via the Meta Model API or a deterministic stub.

    Returns the stub when offline (see ``app.config.parse_offline``) or
    when no ``META_API_KEY`` is set; otherwise POSTs once via httpx.
    ``max_tokens`` is clamped into ``[1, MAX_TOKENS_CAP]`` on every path.
    """
    try:
        clamped = max(1, min(int(max_tokens), MAX_TOKENS_CAP))
    except (TypeError, ValueError):
        clamped = DEFAULT_MAX_TOKENS
    key = os.environ.get("META_API_KEY", "")
    if parse_offline(os.environ.get("QED_OFFLINE")) or not key.strip():
        return _stub(prompt)
    import httpx

    url = os.environ.get("META_API_URL", "") or API_URL
    response = httpx.post(
        url,
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": clamped,
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    try:
        data = response.json()
    except ValueError:
        return _stub(prompt)
    if isinstance(data, dict):
        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                message = first.get("message")
                if isinstance(message, dict):
                    content = message.get("content")
                    if isinstance(content, str) and content:
                        return content
                text = first.get("text")
                if isinstance(text, str) and text:
                    return text
    return _stub(prompt)
