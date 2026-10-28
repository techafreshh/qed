"""Offline tests for the deterministic verdict rubric (PRD section 10)."""

import pytest

from rubric import decide as decide_from_package
from rubric.verdict import Verdict, decide


def test_reexports_match():
    assert decide_from_package is decide


def test_return_shape_is_two_tuple_with_attributes():
    result = decide(2.0, 2.05, 0.01, 0.02, [])
    assert isinstance(result, Verdict)
    verdict, fragile_choice = result
    assert verdict == "REPLICATED"
    assert result[0] == "REPLICATED"
    assert result.verdict == "REPLICATED"
    assert result[1] == fragile_choice == ""


def test_replicated_within_tolerance():
    # Issue acceptance: claimed 2.0 reproduced 2.05, same sign+significance.
    verdict, fragile_choice = decide(2.0, 2.05, 0.01, 0.02, [])
    assert verdict == "REPLICATED"
    assert fragile_choice == ""
    assert isinstance(fragile_choice, str)


def test_replicated_accepts_bool_significance():
    verdict, fragile_choice = decide(2.0, 2.05, True, True, None)
    assert verdict == "REPLICATED"
    assert fragile_choice == ""


def test_replicated_at_exact_tolerance_boundary():
    # Exactly +/-10% still replicates: 2.0 -> 2.2 and 2.0 -> 1.8.
    for reproduced in (2.2, 1.8):
        verdict, fragile_choice = decide(2.0, reproduced, 0.01, 0.02, [])
        assert verdict == "REPLICATED", reproduced
        assert fragile_choice == ""


def test_partial_when_magnitude_40pct_off():
    # Issue acceptance: same sign+significance, magnitude 40% off.
    verdict, fragile_choice = decide(2.0, 2.8, 0.01, 0.02, [])
    assert verdict == "PARTIAL"
    assert isinstance(fragile_choice, str) and fragile_choice != ""


def test_partial_just_outside_tolerance():
    verdict, fragile_choice = decide(2.0, 2.25, 0.01, 0.03, [])
    assert verdict == "PARTIAL"
    assert fragile_choice != ""


def test_failed_on_sign_flip():
    verdict, fragile_choice = decide(2.0, -1.9, 0.01, 0.02, [])
    assert verdict == "FAILED"
    assert isinstance(fragile_choice, str) and fragile_choice != ""


def test_failed_on_significance_loss():
    # Issue acceptance: p 0.01 -> 0.31 loses the alpha=0.05 band.
    verdict, fragile_choice = decide(2.0, 1.95, 0.01, 0.31, [])
    assert verdict == "FAILED"
    assert isinstance(fragile_choice, str) and fragile_choice != ""


def test_failed_on_significance_gain_is_band_change():
    verdict, fragile_choice = decide(2.0, 1.95, 0.31, 0.01, [])
    assert verdict == "FAILED"
    assert fragile_choice != ""


def test_partial_on_grid_subset_break():
    grid = [
        {"estimate": 2.03, "p": 0.02, "choice": "baseline"},
        {"estimate": 1.98, "p": 0.04, "choice": "controls in"},
        {"estimate": -0.4, "p": 0.42, "choice": "with 2020 included"},
    ]
    verdict, fragile_choice = decide(2.0, 2.05, 0.01, 0.02, grid)
    assert verdict == "PARTIAL"
    assert isinstance(fragile_choice, str) and fragile_choice != ""
    assert "with 2020 included" in fragile_choice


def test_failed_on_grid_majority_break():
    grid = [
        {"estimate": -0.4, "p_value": 0.42, "label": "window A"},
        {"estimate": -0.2, "p_value": 0.35, "label": "window B"},
        {"estimate": 2.01, "p_value": 0.02, "label": "baseline"},
    ]
    verdict, fragile_choice = decide(2.0, 2.05, 0.01, 0.02, grid)
    assert verdict == "FAILED"
    assert isinstance(fragile_choice, str) and fragile_choice != ""


def test_failed_headline_partial_upgraded_by_grid_majority():
    grid = [
        {"estimate": -0.5, "significant": False, "choice": "controls in"},
        {"estimate": -0.3, "significant": False, "choice": "window B"},
        {"estimate": 2.6, "significant": True, "choice": "baseline"},
    ]
    verdict, fragile_choice = decide(2.0, 2.8, True, True, grid)
    assert verdict == "FAILED"
    assert fragile_choice != ""


def test_grid_significance_loss_breaks_subset():
    grid = [
        {"reproduced": 2.02, "is_significant": True, "spec": "baseline"},
        {"reproduced": 1.9, "is_significant": False, "spec": "excluding 2020"},
        {"reproduced": 2.04, "is_significant": True, "spec": "window B"},
    ]
    verdict, fragile_choice = decide(2.0, 2.05, 0.01, 0.02, grid)
    assert verdict == "PARTIAL"
    assert "excluding 2020" in fragile_choice


def test_ragged_grid_cells_never_break_or_raise():
    grid = [
        {"note": "no estimate here"},
        {"estimate": "n/a", "choice": "broken cell"},
        None,
        "junk",
        2.04,
    ]
    verdict, fragile_choice = decide(2.0, 2.05, 0.01, 0.02, grid)
    assert verdict == "REPLICATED"
    assert fragile_choice == ""


def test_failed_on_nonfinite_reproduced():
    verdict, fragile_choice = decide(2.0, float("nan"), 0.01, 0.02, [])
    assert verdict == "FAILED"
    assert fragile_choice != ""


def test_exact_at_reported_rounding_replicates():
    # Claimed 2.0 (one decimal) vs 2.04: within half a unit of last place.
    verdict, fragile_choice = decide(2.0, 2.04, 0.01, 0.02, [])
    assert verdict == "REPLICATED"
    assert fragile_choice == ""


def test_zero_headline_uses_absolute_error():
    verdict, _ = decide(0.0, 0.0, 0.6, 0.7, [])
    assert verdict == "REPLICATED"
    verdict, fragile_choice = decide(0.0, 0.5, 0.6, 0.7, [])
    assert verdict == "FAILED"
    assert fragile_choice != ""
