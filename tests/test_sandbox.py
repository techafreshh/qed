"""Offline tests for the Modal sandbox runner (issue #14)."""

import os
import sys
import time
import types

import pytest

from runner import RunResult, run_code
from runner.sandbox import PIP_EGRESS_ALLOWLIST
from runner.sandbox import run_code as sandbox_run_code


def _scrubbed_env(monkeypatch, **overrides):
    for key in ("QED_OFFLINE", "MODAL_TOKEN", "MODAL_TOKEN_ID",
                "MODAL_SECRET"):
        monkeypatch.delenv(key, raising=False)
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)


def test_package_reexport_matches():
    assert sandbox_run_code is run_code


def test_fake_print_hi_is_captured(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    started = time.monotonic()
    result = run_code("print('hi')", "stats")
    elapsed = time.monotonic() - started
    assert isinstance(result, RunResult)
    assert result.exit_code == 0
    assert result.exit == 0
    assert "hi" in result.stdout
    assert result.duration_s >= 0
    assert elapsed < 10.0
    assert isinstance(result.notebook, dict)
    assert result.notebook.get("nbformat") == 4
    assert "hi" in str(result.notebook)
    assert isinstance(result.cell_outputs, list)
    assert any("hi" in str(part) for part in result.cell_outputs)
    assert result.stderr == "" or isinstance(result.stderr, str)


def test_dockerfiles_exist_and_pin_python312():
    for name in ("stats", "ml"):
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            "runner", "images", "%s.Dockerfile" % name)
        assert os.path.isfile(path), "missing %s" % path
        with open(path, encoding="utf-8") as handle:
            content = handle.read()
        assert "FROM python:3.12" in content


def test_unknown_image_raises_value_error(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    with pytest.raises(ValueError):
        run_code("print('hi')", "nope")


def test_error_snippet_returns_nonzero_without_raising(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    result = run_code("1/0", "stats")
    assert result.exit_code != 0
    assert isinstance(result.stderr, str) and result.stderr != ""
    assert isinstance(result.notebook, dict)


def test_data_files_are_mounted(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    result = run_code("print(open('in.txt').read().strip())", "stats",
                      data={"in.txt": b"hello-data"})
    assert result.exit_code == 0
    assert "hello-data" in result.stdout


def test_offline_never_imports_modal(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    run_code("print('hi')", "ml")
    assert "modal" not in sys.modules


def _install_fake_modal(monkeypatch, calls, exit_code=0):
    """Install a mock ``modal`` module recording live-path call shapes."""

    class _FakeReader:
        def __init__(self, text):
            self._text = text

        def read(self):
            return self._text

    class _FakeProc:
        def __init__(self):
            self._stdout = _FakeReader("hi\n")
            self._stderr = _FakeReader("")

        def wait(self, *args, **kwargs):
            calls["wait_args"] = args
            calls["wait_kwargs"] = kwargs
            return exit_code

        @property
        def stdout(self):
            return self._stdout

        @property
        def stderr(self):
            return self._stderr

    class _FakeFilesystem:
        def write_bytes(self, data, remote_path):
            calls.setdefault("writes", []).append((data, remote_path))

    class _FakeSandbox:
        def __init__(self):
            self.filesystem = _FakeFilesystem()

        def exec(self, *args, **kwargs):
            calls["exec_args"] = args
            calls["exec_kwargs"] = kwargs
            return _FakeProc()

        def terminate(self, *args, **kwargs):
            calls["terminated"] = True

    class _FakeSandboxCls:
        @staticmethod
        def create(**kwargs):
            calls["create_kwargs"] = kwargs
            return _FakeSandbox()

    class _FakeImage:
        @staticmethod
        def from_dockerfile(path, **kwargs):
            calls["dockerfile"] = str(path)
            return object()

    fake_modal = types.ModuleType("modal")
    fake_modal.Sandbox = _FakeSandboxCls
    fake_modal.Image = _FakeImage
    monkeypatch.setitem(sys.modules, "modal", fake_modal)


def test_live_path_uses_locked_modal_call_shape(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="0", MODAL_TOKEN="fake")
    calls = {}
    _install_fake_modal(monkeypatch, calls)
    result = run_code("print('hi')", "stats", data={"in.txt": b"hi"})
    assert result.exit_code == 0
    assert "hi" in result.stdout
    create_kwargs = calls["create_kwargs"]
    # Seconds, not milliseconds: a 300s timebox is a 300s lifetime.
    assert create_kwargs["timeout"] == 300
    assert (create_kwargs["outbound_domain_allowlist"]
            == PIP_EGRESS_ALLOWLIST)
    assert "network_egress_allowlist" not in create_kwargs
    assert calls["exec_args"] == ("python3", "-c", "print('hi')")
    assert calls["exec_kwargs"]["timeout"] == 300
    # ContainerProcess.wait() takes no timeout argument.
    assert calls["wait_args"] == ()
    assert calls["wait_kwargs"] == {}
    assert calls["writes"] == [(b"hi", "/tmp/in.txt")]
    assert calls.get("terminated") is True
    assert str(calls["dockerfile"]).endswith("stats.Dockerfile")


def test_live_path_timeout_maps_to_hard_kill(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="0", MODAL_TOKEN="fake")
    calls = {}
    _install_fake_modal(monkeypatch, calls, exit_code=-1)
    result = run_code("print('hi')", "ml")
    assert result.exit_code == 124
    assert "hard kill" in result.stderr
