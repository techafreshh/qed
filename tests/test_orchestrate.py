"""Offline tests for the claim-to-verdict orchestrator (issue #19)."""

import json
import re
import subprocess
import time
from datetime import datetime

import pytest

from agent import run_claim
from agent.orchestrate import MAX_DEBUG_ATTEMPTS


def _scrubbed_env(monkeypatch, **overrides):
    for key in (
        "META_API_KEY",
        "META_API_URL",
        "MODAL_TOKEN",
        "QED_OFFLINE",
        "QED_CODEGEN_BACKEND",
        "OPENCODE_INVOKED_BY",
        "QED_AGENT_DEPTH",
    ):
        monkeypatch.delenv(key, raising=False)
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)


def _forbid_subprocess(monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("subprocess must not run offline")

    for name in ("Popen", "run", "call", "check_call", "check_output"):
        monkeypatch.setattr(subprocess, name, _boom)


def _assert_trace_shape(result):
    trace = result["trace"]
    assert [entry["stage"] for entry in trace] == [
        "extraction",
        "codegen",
        "sandbox",
        "verdict",
    ]
    for entry in trace:
        assert isinstance(entry["ts"], str) and entry["ts"].strip()
        datetime.fromisoformat(entry["ts"])
        assert isinstance(entry["detail"], dict)
    json.dumps(result)


def test_replicated_trace_shape(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    _forbid_subprocess(monkeypatch)
    result = run_claim("demo_replicated", "wages rise with minimum wage")
    assert result["verdict"] == "REPLICATED"
    _assert_trace_shape(result)


def test_failed_fragile_choice(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    _forbid_subprocess(monkeypatch)
    result = run_claim("demo_failed", "wages rise with minimum wage")
    assert result["verdict"] == "FAILED"
    assert isinstance(result["fragile_choice"], str) and result["fragile_choice"].strip()
    _assert_trace_shape(result)


def test_run_log_fields(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    _forbid_subprocess(monkeypatch)
    result = run_claim("demo_replicated", "some claim")
    assert re.fullmatch(r"[0-9a-f]{64}", result["code_sha256"])
    assert isinstance(result["image_digest"], str) and result["image_digest"].strip()
    assert isinstance(result["duration_s"], float)
    assert result["duration_s"] < 60
    assert result["notebook"]["nbformat"] == 4
    assert any(cell["cell_type"] == "code" for cell in result["notebook"]["cells"])


def test_debug_cap_and_duration(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    _forbid_subprocess(monkeypatch)
    start = time.monotonic()
    result = run_claim("demo_replicated", "some claim")
    assert time.monotonic() - start < 60
    assert result["attempts"] <= MAX_DEBUG_ATTEMPTS == 3


def test_ragged_input(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    _forbid_subprocess(monkeypatch)
    with pytest.raises(ValueError):
        run_claim("", "some claim")
    with pytest.raises(ValueError):
        run_claim("   ", "some claim")
    result = run_claim("demo_replicated", "")
    assert result["verdict"] == "REPLICATED"
    _assert_trace_shape(result)
