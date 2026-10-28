import inspect
import subprocess
import time

import pytest

import codegen
import codegen.base
from codegen import (
    CodegenBackend,
    LlamaDirectBackend,
    MuseBackend,
    PiBackend,
    RecursionGuardError,
    check_recursion_guard,
)

_BACKEND_CLASSES = (MuseBackend, PiBackend, LlamaDirectBackend)


def _scrubbed_env(monkeypatch):
    for key in ("OPENCODE_INVOKED_BY", "QED_AGENT_DEPTH"):
        monkeypatch.delenv(key, raising=False)


def _forbid_subprocess(monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("subprocess must not run during guarded author()")

    for name in ("Popen", "run", "call", "check_call", "check_output"):
        monkeypatch.setattr(subprocess, name, _boom)


def test_guard_importable_from_both_packages():
    assert codegen.RecursionGuardError is RecursionGuardError
    assert codegen.base.RecursionGuardError is RecursionGuardError
    assert codegen.check_recursion_guard is check_recursion_guard


def test_interface_signature():
    assert issubclass(MuseBackend, CodegenBackend)
    assert issubclass(PiBackend, CodegenBackend)
    assert issubclass(LlamaDirectBackend, CodegenBackend)
    params = list(inspect.signature(CodegenBackend.author).parameters)
    assert params == ["self", "spec", "dataset_profile", "prior_traceback"]
    default = inspect.signature(CodegenBackend.author).parameters[
        "prior_traceback"
    ].default
    assert default is None


def test_guard_passes_when_unset_empty_whitespace(monkeypatch):
    for value in (None, "", "   ", "\t\n "):
        _scrubbed_env(monkeypatch)
        if value is not None:
            monkeypatch.setenv("OPENCODE_INVOKED_BY", value)
            monkeypatch.setenv("QED_AGENT_DEPTH", value)
        check_recursion_guard()


@pytest.mark.parametrize("backend_cls", _BACKEND_CLASSES)
def test_author_refuses_opencode_var(monkeypatch, backend_cls):
    _scrubbed_env(monkeypatch)
    _forbid_subprocess(monkeypatch)
    monkeypatch.setenv("OPENCODE_INVOKED_BY", "1")
    backend = backend_cls()
    start = time.monotonic()
    with pytest.raises(RecursionGuardError):
        backend.author({"claim": "x"}, {"n": 1})
    assert time.monotonic() - start < 1.0


@pytest.mark.parametrize("backend_cls", _BACKEND_CLASSES)
def test_author_refuses_depth_var(monkeypatch, backend_cls):
    _scrubbed_env(monkeypatch)
    _forbid_subprocess(monkeypatch)
    monkeypatch.setenv("QED_AGENT_DEPTH", "2")
    backend = backend_cls()
    start = time.monotonic()
    with pytest.raises(RecursionGuardError):
        backend.author({"claim": "x"}, {"n": 1})
    assert time.monotonic() - start < 1.0


@pytest.mark.parametrize("backend_cls", _BACKEND_CLASSES)
def test_author_offline_happy_path(monkeypatch, backend_cls):
    _scrubbed_env(monkeypatch)
    _forbid_subprocess(monkeypatch)
    backend = backend_cls()
    code = backend.author({"claim": "x"}, {"n": 1})
    assert isinstance(code, str)
    assert code.strip() != ""
    assert "def " in code
    compile(code, "<offline-stub>", "exec")
