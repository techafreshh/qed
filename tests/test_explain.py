"""Offline tests for Llama verdict narration (issue #17)."""

import time

from agent import explain as package_explain
from agent.explain import EXPLAIN_MAX_TOKENS, explain


def _scrubbed_env(monkeypatch, **overrides):
    for key in ("META_API_KEY", "META_API_URL", "QED_OFFLINE"):
        monkeypatch.delenv(key, raising=False)
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)


def test_package_reexport_matches():
    assert package_explain is explain


def test_max_tokens_is_small():
    assert EXPLAIN_MAX_TOKENS <= 128


def test_offline_names_verdict_and_fragile_choice(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    text = explain("FAILED", [], "excluding 2020; with 2020 p=0.31")
    assert "FAILED" in text
    assert "2020" in text


def test_offline_is_fast_with_zero_llm_calls(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")

    def _boom(prompt, *args, **kwargs):
        raise AssertionError("explain must not call the model offline")

    started = time.monotonic()
    text = explain("FAILED", [], "excluding 2020; with 2020 p=0.31", complete_fn=_boom)
    elapsed = time.monotonic() - started
    assert "FAILED" in text and "2020" in text
    assert elapsed < 2.0


def test_offline_is_deterministic(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    first = explain("FAILED", [], "excluding 2020; with 2020 p=0.31")
    second = explain("FAILED", [], "excluding 2020; with 2020 p=0.31")
    assert first == second
    assert isinstance(first, str) and first != ""
