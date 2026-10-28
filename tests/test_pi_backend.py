"""Offline tests for the pi CLI subprocess codegen backend (issue #12)."""

import shutil
import subprocess
import time

import pytest

from codegen.base import RecursionGuardError
from codegen.pi_backend import CodegenUnavailable, PiBackend
from codegen.pi_backend import PROMPT_TEMPLATE


def _scrubbed_env(monkeypatch, **overrides):
    for key in (
        "META_API_KEY",
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
        raise AssertionError("subprocess must not run on this path")

    for name in ("Popen", "run", "call", "check_call", "check_output"):
        monkeypatch.setattr(subprocess, name, _boom)


def _assert_valid_template(code):
    assert isinstance(code, str)
    assert code.strip() != ""
    assert "def " in code
    assert "def analyze" in code
    assert "# backend=pi" in code
    compile(code, "<pi-backend>", "exec")


def test_offline_returns_template_without_subprocess(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    monkeypatch.setattr(shutil, "which", lambda name: None)
    _forbid_subprocess(monkeypatch)
    start = time.monotonic()
    code = PiBackend().author({"claim": "x"}, {"n": 1})
    assert time.monotonic() - start < 5.0
    _assert_valid_template(code)


def test_offline_unset_env_returns_template_without_subprocess(monkeypatch):
    _scrubbed_env(monkeypatch)
    monkeypatch.setattr(shutil, "which", lambda name: None)
    _forbid_subprocess(monkeypatch)
    start = time.monotonic()
    code = PiBackend().author({"claim": "x"}, {"n": 1})
    assert time.monotonic() - start < 5.0
    _assert_valid_template(code)


def test_missing_binary_online_returns_template(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="0")
    monkeypatch.setattr(shutil, "which", lambda name: None)
    _forbid_subprocess(monkeypatch)
    start = time.monotonic()
    code = PiBackend().author({"claim": "x"}, {"n": 1})
    assert time.monotonic() - start < 5.0
    _assert_valid_template(code)


def test_guard_refuses_before_subprocess(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1", OPENCODE_INVOKED_BY="1")

    def _boom(*args, **kwargs):
        raise AssertionError("subprocess must not run under guard")

    monkeypatch.setattr(subprocess, "run", _boom)
    monkeypatch.setattr(shutil, "which", _boom)
    start = time.monotonic()
    with pytest.raises(RecursionGuardError):
        PiBackend().author({"claim": "x"}, {"n": 1})
    assert time.monotonic() - start < 5.0


def test_guard_depth_refuses_before_subprocess(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1", QED_AGENT_DEPTH="2")

    def _boom(*args, **kwargs):
        raise AssertionError("subprocess must not run under guard")

    monkeypatch.setattr(subprocess, "run", _boom)
    monkeypatch.setattr(shutil, "which", _boom)
    with pytest.raises(RecursionGuardError):
        PiBackend().author({"claim": "x"}, {"n": 1})


def test_timeout_maps_to_unavailable(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="0")
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/pi")

    def _timeout(*args, **kwargs):
        assert kwargs.get("timeout") == 60
        raise subprocess.TimeoutExpired(cmd=args[0] if args else "pi", timeout=60)

    monkeypatch.setattr(subprocess, "run", _timeout)
    with pytest.raises(CodegenUnavailable):
        PiBackend().author({"claim": "x"}, {"n": 1})


def test_nonzero_exit_maps_to_unavailable(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="0")
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/pi")

    def _fail(*args, **kwargs):
        assert kwargs.get("timeout") == 60
        return subprocess.CompletedProcess(
            args=args[0] if args else ["pi"], returncode=1, stdout="", stderr="boom"
        )

    monkeypatch.setattr(subprocess, "run", _fail)
    with pytest.raises(CodegenUnavailable):
        PiBackend().author({"claim": "x"}, {"n": 1})


def test_blank_stdout_maps_to_unavailable(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="0")
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/pi")

    def _blank(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0] if args else ["pi"], returncode=0, stdout="   \n", stderr=""
        )

    monkeypatch.setattr(subprocess, "run", _blank)
    with pytest.raises(CodegenUnavailable):
        PiBackend().author({"claim": "x"}, {"n": 1})


def test_live_success_returns_stdout(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="0")
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/pi")
    expected = "def analyze(spec=None, dataset_profile=None):\n    return {}\n"

    def _ok(*args, **kwargs):
        assert list(args[0][:2]) == ["pi", "-p"]
        assert kwargs.get("timeout") == 60
        return subprocess.CompletedProcess(
            args=args[0], returncode=0, stdout=expected, stderr=""
        )

    monkeypatch.setattr(subprocess, "run", _ok)
    assert PiBackend().author({"claim": "x"}, {"n": 1}) == expected.strip()


def test_prompt_template_is_pinned():
    assert "{spec}" in PROMPT_TEMPLATE
    assert "{profile}" in PROMPT_TEMPLATE
    assert "{traceback}" in PROMPT_TEMPLATE
    assert "replication analysis" in PROMPT_TEMPLATE.lower()
