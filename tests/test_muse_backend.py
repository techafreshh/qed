"""Offline tests for the muse codegen backend and factory (issue #13)."""

import shutil
import subprocess
import time

import pytest

from codegen.base import RecursionGuardError
from codegen.factory import BACKENDS, get_backend
from codegen.muse_backend import MUSE_MODEL, CodegenUnavailable, MuseBackend
from codegen.muse_backend import PROMPT_TEMPLATE


def _scrubbed_env(monkeypatch, **overrides):
    for key in (
        "META_API_KEY",
        "MODAL_TOKEN",
        "QED_OFFLINE",
        "QED_CODEGEN_BACKEND",
        "QED_MUSE_MODEL",
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
    assert "# backend=muse" in code
    compile(code, "<muse-backend>", "exec")


def test_offline_returns_template_without_subprocess(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    monkeypatch.setattr(shutil, "which", lambda name: None)
    _forbid_subprocess(monkeypatch)
    start = time.monotonic()
    code = MuseBackend().author({"claim": "x"}, {"n": 1})
    assert time.monotonic() - start < 5.0
    _assert_valid_template(code)


def test_offline_unset_env_returns_template_without_subprocess(monkeypatch):
    _scrubbed_env(monkeypatch)
    monkeypatch.setattr(shutil, "which", lambda name: None)
    _forbid_subprocess(monkeypatch)
    start = time.monotonic()
    code = MuseBackend().author({"claim": "x"}, {"n": 1})
    assert time.monotonic() - start < 5.0
    _assert_valid_template(code)


def test_missing_binary_online_returns_template(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="0")
    monkeypatch.setattr(shutil, "which", lambda name: None)
    _forbid_subprocess(monkeypatch)
    start = time.monotonic()
    code = MuseBackend().author({"claim": "x"}, {"n": 1})
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
        MuseBackend().author({"claim": "x"}, {"n": 1})
    assert time.monotonic() - start < 5.0


def test_guard_depth_refuses_before_subprocess(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1", QED_AGENT_DEPTH="2")

    def _boom(*args, **kwargs):
        raise AssertionError("subprocess must not run under guard")

    monkeypatch.setattr(subprocess, "run", _boom)
    monkeypatch.setattr(shutil, "which", _boom)
    with pytest.raises(RecursionGuardError):
        MuseBackend().author({"claim": "x"}, {"n": 1})


def test_timeout_maps_to_unavailable(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="0")
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/pi")

    def _timeout(*args, **kwargs):
        assert kwargs.get("timeout") == 60
        raise subprocess.TimeoutExpired(cmd=args[0] if args else "pi", timeout=60)

    monkeypatch.setattr(subprocess, "run", _timeout)
    with pytest.raises(CodegenUnavailable):
        MuseBackend().author({"claim": "x"}, {"n": 1})


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
        MuseBackend().author({"claim": "x"}, {"n": 1})


def test_blank_stdout_maps_to_unavailable(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="0")
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/pi")

    def _blank(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0] if args else ["pi"], returncode=0, stdout="   \n", stderr=""
        )

    monkeypatch.setattr(subprocess, "run", _blank)
    with pytest.raises(CodegenUnavailable):
        MuseBackend().author({"claim": "x"}, {"n": 1})


def test_live_success_returns_stdout_with_model_argv(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="0")
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/pi")
    expected = "def analyze(spec=None, dataset_profile=None):\n    return {}\n"

    def _ok(*args, **kwargs):
        argv = list(args[0])
        assert argv[0] == "pi"
        assert "--model" in argv
        assert MUSE_MODEL in argv
        assert MUSE_MODEL == "muse-spark-1.3-contributor"
        assert "-p" in argv
        assert kwargs.get("timeout") == 60
        return subprocess.CompletedProcess(
            args=args[0], returncode=0, stdout=expected, stderr=""
        )

    monkeypatch.setattr(subprocess, "run", _ok)
    assert MuseBackend().author({"claim": "x"}, {"n": 1}) == expected.strip()


def test_model_override_env_reaches_argv(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="0", QED_MUSE_MODEL="custom-model")
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/pi")
    expected = "def analyze(spec=None, dataset_profile=None):\n    return {}\n"
    seen = {}

    def _ok(*args, **kwargs):
        seen["argv"] = list(args[0])
        return subprocess.CompletedProcess(
            args=args[0], returncode=0, stdout=expected, stderr=""
        )

    monkeypatch.setattr(subprocess, "run", _ok)
    MuseBackend().author({"claim": "x"}, {"n": 1})
    assert "custom-model" in seen["argv"]
    assert MUSE_MODEL not in seen["argv"]


def test_prompt_template_is_pinned():
    assert "{spec}" in PROMPT_TEMPLATE
    assert "{profile}" in PROMPT_TEMPLATE
    assert "{traceback}" in PROMPT_TEMPLATE
    assert "replication analysis" in PROMPT_TEMPLATE.lower()


def test_factory_backends_map():
    assert set(BACKENDS) == {"muse", "pi", "llama_direct"}


@pytest.mark.parametrize("name", ["muse", "pi", "llama_direct"])
def test_factory_returns_backend_with_author(monkeypatch, name):
    _scrubbed_env(monkeypatch)
    backend = get_backend(name)
    assert callable(getattr(backend, "author", None))


@pytest.mark.parametrize("name", [" Muse ", "PI", "Llama_Direct"])
def test_factory_names_are_case_and_whitespace_tolerant(monkeypatch, name):
    _scrubbed_env(monkeypatch)
    backend = get_backend(name)
    assert callable(getattr(backend, "author", None))


def test_factory_env_default_selects_muse(monkeypatch):
    _scrubbed_env(monkeypatch, QED_CODEGEN_BACKEND="muse")
    backend = get_backend()
    assert isinstance(backend, MuseBackend)


def test_factory_blank_name_falls_back_to_env(monkeypatch):
    _scrubbed_env(monkeypatch, QED_CODEGEN_BACKEND="pi")
    assert callable(getattr(get_backend("   "), "author", None))


def test_factory_unknown_name_raises_unavailable(monkeypatch):
    _scrubbed_env(monkeypatch)
    with pytest.raises(CodegenUnavailable):
        get_backend("nope")


def test_factory_muse_author_offline_fast(monkeypatch):
    _scrubbed_env(monkeypatch, QED_CODEGEN_BACKEND="muse", QED_OFFLINE="1")
    monkeypatch.setattr(shutil, "which", lambda name: None)
    _forbid_subprocess(monkeypatch)
    start = time.monotonic()
    try:
        code = get_backend("muse").author({"claim": "x"}, {"n": 1})
    except CodegenUnavailable:
        code = ""
        assert time.monotonic() - start < 5.0
        return
    assert time.monotonic() - start < 5.0
    assert isinstance(code, str)
    assert code.strip() != ""
    compile(code, "<muse-factory>", "exec")
