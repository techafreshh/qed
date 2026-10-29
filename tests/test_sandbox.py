"""Offline tests for the Modal sandbox runner (issue #14)."""

import os
import sys
import time

import pytest

from runner import RunResult, run_code
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
