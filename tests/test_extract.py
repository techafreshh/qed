"""Offline tests for claim extraction (issue #8)."""

import json

import pytest

from agent import ExtractionFailed, extract
from agent.extract import Spec


def _scrubbed_env(monkeypatch, **overrides):
    for key in ("META_API_KEY", "META_API_URL", "QED_OFFLINE"):
        monkeypatch.delenv(key, raising=False)
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)


SAMPLE_ABSTRACT = (
    "We study the effect of minimum wages on employment using "
    "a difference-in-differences design on payroll data. "
    "Employment rises by 2.0 percentage points (p = 0.01), significant at 5%."
)
SAMPLE_CLAIM = "Minimum wage hikes raise employment by 2 points (p < 0.05)."


def test_offline_returns_spec_keys(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    result = extract(SAMPLE_ABSTRACT, SAMPLE_CLAIM)
    assert isinstance(result, dict)
    for key in ("dataset", "estimator", "headline_numbers", "significance_claim"):
        assert key in result
    Spec.model_validate(result)
    json.dumps(result)


def test_malformed_stub_raises_after_three_attempts(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="0")
    calls = []

    def stub(prompt):
        calls.append(prompt)
        return "not json"

    with pytest.raises(ExtractionFailed):
        extract(SAMPLE_ABSTRACT, SAMPLE_CLAIM, complete_fn=stub)
    assert len(calls) == 3


def test_offline_makes_zero_llm_calls(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")

    def stub(prompt):
        raise AssertionError("LLM must not be called offline")

    result = extract(SAMPLE_ABSTRACT, SAMPLE_CLAIM, complete_fn=stub)
    assert result["dataset"] == "offline-dataset"
