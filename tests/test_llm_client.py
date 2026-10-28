"""Offline tests for the Meta Model API client (issue #7, PRD llama reasoning)."""

import json
import time

from httpx import Response

from agent import complete as package_complete
from agent.llm import API_URL, DEFAULT_MAX_TOKENS, MAX_TOKENS_CAP, complete


def _scrubbed_env(monkeypatch, **overrides):
    for key in ("META_API_KEY", "META_API_URL", "QED_OFFLINE"):
        monkeypatch.delenv(key, raising=False)
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)


def test_package_reexport_matches():
    assert package_complete is complete


def test_defaults_cap_max_tokens():
    assert DEFAULT_MAX_TOKENS <= 512
    assert MAX_TOKENS_CAP == 512


def test_offline_stub_without_keys_is_fast_and_deterministic(
    monkeypatch, respx_mock
):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    started = time.monotonic()
    result = complete("hello")
    elapsed = time.monotonic() - started
    assert isinstance(result, str) and result != ""
    assert result.startswith("stub:")
    assert "hello" in result
    assert elapsed < 2.0
    assert complete("hello") == result


def test_keyless_online_still_returns_stub_with_zero_egress(
    monkeypatch, respx_mock
):
    _scrubbed_env(monkeypatch, QED_OFFLINE="0")
    result = complete("hello")
    assert isinstance(result, str) and result != ""
    assert result.startswith("stub:")


def test_live_post_sends_clamped_max_tokens(monkeypatch, respx_mock):
    _scrubbed_env(monkeypatch, QED_OFFLINE="0", META_API_KEY="dummy")
    route = respx_mock.post(API_URL).mock(
        return_value=Response(
            200, json={"choices": [{"message": {"content": "live-answer"}}]}
        )
    )
    result = complete("x", max_tokens=4096)
    assert result == "live-answer"
    assert route.called
    assert route.call_count == 1
    body = json.loads(route.calls[0].request.content.decode("utf-8"))
    assert body["max_tokens"] <= 512


def test_live_returns_mocked_choice_text(monkeypatch, respx_mock):
    _scrubbed_env(monkeypatch, QED_OFFLINE="0", META_API_KEY="dummy")
    route = respx_mock.post(API_URL).mock(
        return_value=Response(
            200, json={"choices": [{"message": {"content": "mocked-content"}}]}
        )
    )
    assert complete("hello") == "mocked-content"
    assert route.call_count == 1


def test_default_call_sends_small_max_tokens(monkeypatch, respx_mock):
    _scrubbed_env(monkeypatch, QED_OFFLINE="0", META_API_KEY="dummy")
    route = respx_mock.post(API_URL).mock(
        return_value=Response(200, json={"choices": [{"text": "t"}]})
    )
    complete("hello")
    body = json.loads(route.calls[0].request.content.decode("utf-8"))
    assert body["max_tokens"] <= 512
