"""Offline tests for the receipt notebook builder (issue #18)."""

import json
import os

import pytest

from runner import (
    build_and_execute,
    build_notebook,
    execute_notebook,
    extract_numbers,
)
from runner import notebook as notebook_module

SAMPLE_CODE = 'print("estimate=1.98")'


def _scrubbed_env(monkeypatch, **overrides):
    for key in ("META_API_KEY", "META_API_URL", "MODAL_TOKEN", "QED_OFFLINE"):
        monkeypatch.delenv(key, raising=False)
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)


def _output_text(notebook):
    parts = []
    for cell in notebook.get("cells", []):
        if not isinstance(cell, dict) or cell.get("cell_type") != "code":
            continue
        for output in cell.get("outputs", []) or []:
            parts.extend(notebook_module._output_texts(output))
    return "\n".join(parts)


def test_build_and_execute_captures_estimate(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    notebook = build_and_execute(SAMPLE_CODE, paper_id="demo", claim="c")
    assert isinstance(notebook, dict)
    assert notebook.get("nbformat") == 4
    assert len(notebook.get("cells", [])) >= 2
    assert "1.98" in _output_text(notebook)


def test_saved_notebook_passes_nbformat_validate(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    nbformat = pytest.importorskip("nbformat")
    notebook = build_and_execute(
        SAMPLE_CODE,
        grid_cells=[{"id": "baseline", "description": "Baseline OLS."}],
        paper_id="demo",
        claim="c",
    )
    path = "/tmp/qed_nb.json"
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(notebook, handle)
    with open(path, encoding="utf-8") as handle:
        loaded = json.load(handle)
    nbformat.validate(loaded)
    assert len(loaded["cells"]) >= 2
    assert "1.98" in _output_text(loaded)


def test_ragged_inputs_never_raise(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    notebook = build_and_execute(None, None, None, None)
    assert isinstance(notebook, dict)
    assert notebook.get("nbformat") == 4
    assert isinstance(notebook.get("cells"), list)
    assert len(notebook["cells"]) >= 2
    assert extract_numbers(None) == []
    assert isinstance(build_notebook(123, "not-a-list", 4, 5), dict)
    assert isinstance(execute_notebook(None), dict)
    assert isinstance(execute_notebook({"cells": "ragged"}), dict)
    assert isinstance(execute_notebook({"nbformat": 4}), dict)


def test_extract_numbers_recovers_estimate(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    notebook = build_and_execute(SAMPLE_CODE)
    numbers = extract_numbers(notebook)
    assert isinstance(numbers, list)
    assert all(isinstance(value, float) for value in numbers)
    assert 1.98 in numbers


def test_grid_cells_accept_dicts_strings_and_objects(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    from agent.grid import GridCell

    grid = [
        GridCell(id="baseline", description="Baseline OLS."),
        {"id": "controls-in", "description": "With controls."},
        "free-form robustness note",
        None,
        42,
    ]
    notebook = build_and_execute(SAMPLE_CODE, grid_cells=grid)
    assert len(notebook["cells"]) == 2 + len(grid)
    assert "1.98" in _output_text(notebook)


def test_failing_code_reports_error_without_raising(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    notebook = build_and_execute("1/0")
    assert len(notebook["cells"]) >= 2
    code_cells = [cell for cell in notebook["cells"]
                  if cell.get("cell_type") == "code"]
    assert code_cells
    assert any(cell.get("outputs") for cell in code_cells)


def test_environ_offline_default_without_qed_offline(monkeypatch):
    for key in ("META_API_KEY", "META_API_URL", "MODAL_TOKEN", "QED_OFFLINE"):
        monkeypatch.delenv(key, raising=False)
    assert os.environ.get("QED_OFFLINE") is None
    notebook = build_and_execute(SAMPLE_CODE)
    assert "1.98" in _output_text(notebook)
