"""Offline tests for the llama_direct codegen backend (issue #11)."""

import subprocess
import sys
import time
from pathlib import Path

import pytest

import codegen.llama_backend
from codegen import LlamaBackend
from codegen.llama_backend import LlamaBackend as DirectLlamaBackend
from codegen.llama_backend import RecursionGuardError


@pytest.fixture
def spec_fixture():
    return {
        "id": "spec-001",
        "claim": "minimum wage raises employment",
        "estimator": "OLS",
    }


@pytest.fixture
def profile_fixture():
    return {"path": "data.csv", "n_rows": 1000, "columns": ["wage", "employed"]}


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
        raise AssertionError("subprocess must not run during author()")

    for name in ("Popen", "run", "call", "check_call", "check_output"):
        monkeypatch.setattr(subprocess, name, _boom)


def _assert_valid_script(code):
    assert isinstance(code, str)
    assert "import pandas" in code
    assert "statsmodels" in code
    assert len(code) > 200
    compile(code, "<llama-backend>", "exec")


def test_reexport_matches(monkeypatch):
    _scrubbed_env(monkeypatch)
    assert LlamaBackend is DirectLlamaBackend
    assert codegen.llama_backend.LlamaBackend is DirectLlamaBackend


def test_offline_author_contains_pandas_and_statsmodels(
    monkeypatch, spec_fixture, profile_fixture
):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    result = LlamaBackend().author(spec_fixture, profile_fixture)
    _assert_valid_script(result)


def test_offline_output_compiles(
    monkeypatch, spec_fixture, profile_fixture, tmp_path
):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    result = LlamaBackend().author(spec_fixture, profile_fixture)
    target = Path("/tmp/qed_codegen_test.py")
    target.write_text(result, encoding="utf-8")
    try:
        assert target.exists()
        proc = subprocess.run(
            [sys.executable, "-m", "py_compile", str(target)],
            capture_output=True,
        )
        assert proc.returncode == 0
    finally:
        target.unlink(missing_ok=True)


def test_recursion_guard_open_code(monkeypatch, spec_fixture, profile_fixture):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1", OPENCODE_INVOKED_BY="1")
    _forbid_subprocess(monkeypatch)
    start = time.monotonic()
    with pytest.raises(RecursionGuardError):
        LlamaBackend().author(spec_fixture, profile_fixture)
    assert time.monotonic() - start < 1.0


def test_recursion_guard_depth(monkeypatch, spec_fixture, profile_fixture):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1", QED_AGENT_DEPTH="2")
    _forbid_subprocess(monkeypatch)
    start = time.monotonic()
    with pytest.raises(RecursionGuardError):
        LlamaBackend().author(spec_fixture, profile_fixture)
    assert time.monotonic() - start < 1.0


def test_offline_default_with_clean_env(monkeypatch):
    _scrubbed_env(monkeypatch)
    _assert_valid_script(LlamaBackend().author({"claim": "x"}, {"n": 1}))


def test_ragged_inputs_never_raise(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    _assert_valid_script(LlamaBackend().author(None, None))
    _assert_valid_script(LlamaBackend().author("x", {"odd": 1}))
    _assert_valid_script(
        LlamaBackend().author(
            {"claim": "x"}, {"n": 1}, prior_traceback="Traceback: boom"
        )
    )
    _assert_valid_script(
        LlamaBackend().author({"claim": "x"}, profile={"n": 1})
    )


def test_live_failure_falls_back(monkeypatch, spec_fixture, profile_fixture):
    _scrubbed_env(
        monkeypatch, QED_OFFLINE="0", META_API_KEY="fake-key-for-test"
    )
    import httpx

    def _boom(*args, **kwargs):
        raise httpx.ConnectError("no network in test")

    monkeypatch.setattr(httpx, "post", _boom)
    start = time.monotonic()
    result = LlamaBackend().author(spec_fixture, profile_fixture)
    assert time.monotonic() - start < 30.0
    _assert_valid_script(result)
