"""Deterministic replication verdict rubric (PRD section 10).

Pure functions only: no network, no model calls, no file I/O,
no clock, no randomness. Depends on the standard library alone.
"""

import math
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

REPLICATED = "REPLICATED"
PARTIAL = "PARTIAL"
FAILED = "FAILED"

ALPHA = 0.05
TOLERANCE = 0.10
ZERO_ABS_TOL = 1e-9
_FLOAT_NOISE = 1e-9


class Verdict(NamedTuple):
    verdict: str
    fragile_choice: str


def _sign(value: float) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _coerce_significance(value: Any) -> Optional[bool]:
    """Map a p-value or an already-thresholded flag to a significance band.

    Returns None when the band cannot be determined (missing/unparseable),
    in which case callers skip the significance comparison.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        number = float(value)
        if math.isnan(number):
            return None
        return number < ALPHA
    if isinstance(value, str):
        text = value.strip().lower()
        if text in ("true", "t", "yes", "y", "significant", "sig", "1"):
            return True
        if text in ("false", "f", "no", "n", "not significant",
                    "n.s.", "ns", "non-significant", "nonsignificant", "0"):
            return False
        try:
            number = float(text)
        except ValueError:
            return None
        if math.isnan(number):
            return None
        return number < ALPHA
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number):
        return None
    return number < ALPHA


def _reported_half_unit(claimed_raw: Any, claimed: float) -> float:
    """Half a unit of the claimed value's last reported decimal place."""
    if isinstance(claimed_raw, bool):
        text = repr(claimed)
    elif isinstance(claimed_raw, int):
        text = str(claimed_raw)
    elif isinstance(claimed_raw, float):
        text = repr(claimed_raw)
    elif isinstance(claimed_raw, str):
        text = claimed_raw.strip()
    else:
        text = repr(claimed)
    try:
        return _half_unit_of_decimal_text(text)
    except ValueError:
        return 0.0


def _half_unit_of_decimal_text(text: str) -> float:
    body = text.strip().lstrip("+-")
    if not body or body.lower() in ("nan", "inf", "infinity"):
        raise ValueError("no decimal places")
    exponent = 0
    mantissa = body
    for marker in ("e", "E"):
        if marker in mantissa:
            mantissa, _, exp_text = mantissa.partition(marker)
            exponent = int(exp_text.strip())
            break
    if "." in mantissa:
        _, _, fraction = mantissa.partition(".")
        decimals = len(fraction) - exponent
    else:
        decimals = -exponent
    if decimals < 0 or decimals > 15:
        raise ValueError("no usable decimal places")
    return 0.5 * (10.0 ** -decimals)


def _within_tolerance(claimed_raw: Any, claimed: float, reproduced: float) -> Tuple[bool, float]:
    """Check the magnitude rule; returns (within, relative_or_absolute_gap)."""
    absolute_gap = abs(reproduced - claimed)
    if claimed == 0.0:
        return absolute_gap <= ZERO_ABS_TOL, absolute_gap
    relative_gap = absolute_gap / abs(claimed)
    if relative_gap <= TOLERANCE + _FLOAT_NOISE:
        return True, relative_gap
    half_unit = _reported_half_unit(claimed_raw, claimed)
    if half_unit > 0.0 and absolute_gap <= half_unit + 1e-12:
        return True, relative_gap
    return False, relative_gap


_ESTIMATE_KEYS = ("estimate", "reproduced", "value", "effect", "coef", "coefficient")
_P_KEYS = ("p", "p_value", "pvalue")
_FLAG_KEYS = ("significant", "is_significant", "sig")
_LABEL_KEYS = ("choice", "label", "spec")


def _cell_estimate(cell: Dict[str, Any]) -> Tuple[bool, Optional[float]]:
    for key in _ESTIMATE_KEYS:
        if key not in cell or cell[key] is None:
            continue
        try:
            return True, float(cell[key])
        except (TypeError, ValueError):
            continue
    return False, None


def _cell_significance(cell: Dict[str, Any]) -> Optional[bool]:
    for key in _P_KEYS:
        if key not in cell or cell[key] is None:
            continue
        try:
            number = float(cell[key])
        except (TypeError, ValueError):
            continue
        if math.isnan(number):
            continue
        return number < ALPHA
    for key in _FLAG_KEYS:
        if key not in cell or cell[key] is None:
            continue
        raw = cell[key]
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            coerced = _coerce_significance(raw)
            if coerced is not None:
                return coerced
            continue
        try:
            return bool(float(raw))
        except (TypeError, ValueError):
            continue
    return None


def _cell_label(cell: Dict[str, Any]) -> Optional[str]:
    for key in _LABEL_KEYS:
        if key not in cell or cell[key] is None:
            continue
        text = str(cell[key]).strip()
        if text:
            return text
    return None


def decide(headline_claimed: Any,
           reproduced: Any,
           p_claimed_sig: Any = None,
           p_repro_sig: Any = None,
           grid_results: Any = None) -> Verdict:
    """Decide REPLICATED / PARTIAL / FAILED for one headline replication.

    Pure function of its arguments. Never raises on ragged grid input:
    unparseable grid cells are treated as non-breaking.
    """
    try:
        claimed = float(headline_claimed)
    except (TypeError, ValueError):
        return Verdict(FAILED, "unparseable headline claim (%r)" % (headline_claimed,))
    try:
        repro = float(reproduced)
    except (TypeError, ValueError):
        return Verdict(FAILED, "unparseable reproduced value (%r)" % (reproduced,))
    if not math.isfinite(claimed):
        return Verdict(FAILED, "non-finite headline claim (%r)" % (headline_claimed,))
    if not math.isfinite(repro):
        return Verdict(FAILED, "non-finite reproduced value (%r)" % (reproduced,))

    claimed_sig = _coerce_significance(p_claimed_sig)
    repro_sig = _coerce_significance(p_repro_sig)

    if _sign(claimed) != _sign(repro):
        return Verdict(
            FAILED,
            "sign flip (claimed %g, reproduced %g)" % (claimed, repro),
        )

    if claimed_sig is not None and repro_sig is not None and claimed_sig != repro_sig:
        return Verdict(
            FAILED,
            "significance band change at alpha=0.05 "
            "(claimed p=%r %s, reproduced p=%r %s)" % (
                p_claimed_sig,
                "significant" if claimed_sig else "not significant",
                p_repro_sig,
                "significant" if repro_sig else "not significant",
            ),
        )

    within, gap = _within_tolerance(headline_claimed, claimed, repro)
    if within:
        provisional: Verdict = Verdict(REPLICATED, "")
        headline_note = ""
    else:
        if claimed == 0.0:
            headline_note = (
                "magnitude gap %g outside absolute tolerance %g "
                "(claimed %g, reproduced %g)" % (gap, ZERO_ABS_TOL, claimed, repro)
            )
        else:
            headline_note = (
                "magnitude gap %.1f%% outside +-10%% tolerance "
                "(claimed %g, reproduced %g)" % (gap * 100.0, claimed, repro)
            )
        provisional = Verdict(PARTIAL, headline_note)

    if grid_results is None:
        return provisional
    try:
        if isinstance(grid_results, dict):
            cells: List[Any] = [grid_results]
        else:
            cells = list(grid_results)
    except TypeError:
        return provisional
    if not cells:
        return provisional

    baseline_sig = claimed_sig if claimed_sig is not None else repro_sig
    breaks: List[str] = []
    for index, cell in enumerate(cells):
        if not isinstance(cell, dict):
            continue
        reasons: List[str] = []
        present, estimate = _cell_estimate(cell)
        if present and estimate is not None:
            if not math.isfinite(estimate):
                reasons.append("non-finite estimate (%r)" % (cell.get("estimate"),))
            elif _sign(estimate) != _sign(claimed):
                reasons.append(
                    "sign flip (headline %g, cell %g)" % (claimed, estimate)
                )
        cell_sig = _cell_significance(cell)
        if (cell_sig is not None and baseline_sig is not None
                and cell_sig != baseline_sig):
            reasons.append(
                "significance change (headline %s, cell %s)" % (
                    "significant" if baseline_sig else "not significant",
                    "significant" if cell_sig else "not significant",
                )
            )
        if not reasons:
            continue
        label = _cell_label(cell)
        reason = "; ".join(reasons)
        if label is not None:
            breaks.append("%s: %s" % (label, reason))
        else:
            breaks.append("cell %d: %s" % (index, reason))

    if not breaks:
        return provisional
    # Strict majority: half the grid breaking (e.g. 1 of 2) still means the
    # result holds under a subset, which is PARTIAL per the rubric.
    if len(breaks) / len(cells) > 0.5:
        return Verdict(FAILED, breaks[0])
    return Verdict(PARTIAL, breaks[0])
