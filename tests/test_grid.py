"""Offline tests for the bounded grid planner (issue #9)."""

import json

from agent import GridCell, plan_grid
from agent.grid import MAX_CELLS
from rubric.verdict import _cell_label

SAMPLE_SPEC = {
    "dataset": "payroll panel 2000-2020",
    "estimator": "OLS",
    "headline_numbers": {"estimate": 2.0, "p_value": 0.01},
    "significance_claim": "p < 0.05",
}


def _scrubbed_env(monkeypatch):
    for key in ("META_API_KEY", "META_API_URL", "QED_OFFLINE"):
        monkeypatch.delenv(key, raising=False)


def test_standard_ols_grid_bounded_2_to_8(monkeypatch):
    _scrubbed_env(monkeypatch)
    cells = plan_grid(SAMPLE_SPEC)
    assert isinstance(cells, list)
    assert 2 <= len(cells) <= 8
    assert len(cells) <= MAX_CELLS
    for cell in cells:
        assert isinstance(cell, GridCell)


def test_controls_variation_and_unique_ids(monkeypatch):
    _scrubbed_env(monkeypatch)
    cells = plan_grid(SAMPLE_SPEC)
    ids = [cell.id for cell in cells]
    assert len(ids) == len(set(ids))
    assert all(isinstance(i, str) and i.strip() for i in ids)
    controls = {cell.controls for cell in cells}
    assert controls == {True, False} or (True in controls and False in controls)


def test_fragile_choice_derivable(monkeypatch):
    _scrubbed_env(monkeypatch)
    cells = plan_grid(SAMPLE_SPEC)
    descriptions = []
    for cell in cells:
        assert isinstance(cell.description, str) and cell.description.strip()
        descriptions.append(cell.description.strip())
        dumped = cell.model_dump(mode="json")
        assert dumped["id"].strip()
        assert dumped["description"].strip()
        assert dumped["choice"].strip()
        assert _cell_label(dumped) and _cell_label(dumped).strip()
        assert _cell_label(cell) and _cell_label(cell).strip()
        json.dumps(dumped)
    assert len(set(descriptions)) == len(descriptions)


def test_ragged_spec_never_raises(monkeypatch):
    _scrubbed_env(monkeypatch)
    for ragged in ({}, None, "junk", 42, [], {"unexpected": "shape"}):
        cells = plan_grid(ragged)
        assert isinstance(cells, list)
        assert 2 <= len(cells) <= 8
        ids = [cell.id for cell in cells]
        assert len(ids) == len(set(ids))
        assert all(cell.description.strip() for cell in cells)
        controls = {cell.controls for cell in cells}
        assert True in controls and False in controls


def test_deterministic_and_json_serializable(monkeypatch):
    _scrubbed_env(monkeypatch)
    first = [cell.model_dump(mode="json") for cell in plan_grid(SAMPLE_SPEC)]
    second = [cell.model_dump(mode="json") for cell in plan_grid(SAMPLE_SPEC)]
    assert first == second
    json.dumps(first)
