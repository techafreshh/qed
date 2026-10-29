"""No-fabrication checker: every card number traces to a cell (issue #28).

Extracts numbers from the verdict card plus offline narration and asserts
each one appears in executed notebook cell outputs (2-decimal rounding
normalization). Exit 0 with ``0 untraced`` iff every card number traces;
exit 1 with ``untraced`` on stdout otherwise; exit 2 on usage errors and
unknown runs. Offline and credential-free: no network, no model calls;
the only subprocesses are the checker's own per-cell executions via
``runner.notebook.execute_notebook``.
"""

from __future__ import annotations

import argparse
import copy
import math
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from agent.explain import explain
from runner.notebook import _NUMBER_RE, execute_notebook, extract_numbers
from runner.offline import NotFound, replay

_YEAR_MIN = 1900
_YEAR_MAX = 2100
_YEAR_RE = re.compile(r"^\d{4}$")


def _coerce_str(value, default=""):
    """Best-effort string coercion; never raises."""
    try:
        if value is None:
            return default
        if isinstance(value, str):
            return value
        return str(value)
    except Exception:
        return default


def build_card_text(result) -> str:
    """Verdict + fragile choice + offline narration; never raises."""
    try:
        data = result if isinstance(result, dict) else {}
        verdict = _coerce_str(data.get("verdict"))
        fragile = _coerce_str(data.get("fragile_choice"))
        try:
            narration = explain(verdict, [], fragile)
        except Exception:
            narration = ""
        narration = _coerce_str(narration)
        parts = [part for part in (verdict, fragile, narration) if part.strip()]
        return "\n".join(parts)
    except Exception:
        return ""


def _is_year(raw: str) -> bool:
    """True for plain 4-digit years 1900-2100; never raises."""
    try:
        if not isinstance(raw, str):
            return False
        token = raw.strip()
        if token[:1] in ("+", "-"):
            return False
        token = token.rstrip(".")  # sentence-final "2020." is still a year
        if not _YEAR_RE.match(token):
            return False
        return _YEAR_MIN <= int(token) <= _YEAR_MAX
    except Exception:
        return False


def extract_card_numbers(text) -> list:
    """Deduped card floats in first-seen order; skips years; never raises."""
    found: list = []
    seen: set = set()
    try:
        matches = _NUMBER_RE.findall(_coerce_str(text))
    except Exception:
        return []
    for raw in matches:
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        try:
            if not math.isfinite(value):
                continue
        except Exception:
            continue
        if _is_year(raw):
            continue
        if value not in seen:
            seen.add(value)
            found.append(value)
    return found


def cell_numbers_for(notebook) -> list:
    """Execute a copy of the notebook, then extract output numbers."""
    try:
        executed = execute_notebook(copy.deepcopy(notebook))
    except Exception:
        return []
    try:
        numbers = extract_numbers(executed)
    except Exception:
        return []
    return numbers if isinstance(numbers, list) else []


def _traces(card_value: float, cell_numbers: list) -> bool:
    """True when a cell number matches at 2-decimal rounding (or exactly)."""
    for cell_value in cell_numbers:
        try:
            if card_value == cell_value:
                return True
        except Exception:
            pass
        try:
            if round(card_value, 2) == round(cell_value, 2):
                return True
        except Exception:
            pass
    return False


def match_numbers(card_numbers, cell_numbers) -> list:
    """Card numbers with no 2-decimal match in cell numbers; never raises."""
    try:
        card = list(card_numbers) if card_numbers else []
    except Exception:
        return []
    try:
        cells = list(cell_numbers) if cell_numbers else []
    except Exception:
        cells = []
    try:
        return [value for value in card if not _traces(value, cells)]
    except Exception:
        return []


def _read_card_file(path) -> str:
    """Read a card-text override file; raises ValueError when unreadable."""
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, TypeError, ValueError) as exc:
        raise ValueError("cannot read card file %r: %s" % (path, exc)) from exc


def check(run_id, card_text=None, card_file=None) -> tuple:
    """Check one cached run; return ``(untraced, card_numbers, cell_numbers)``.

    ``card_text``/``card_file`` override the built verdict-card text
    (doctored-card probing). Raises :class:`NotFound` for unknown runs
    and :class:`ValueError` for unreadable card files.
    """
    run = replay(run_id)
    if card_file:
        text = _read_card_file(card_file)
    elif card_text is not None:
        text = _coerce_str(card_text)
    else:
        text = build_card_text(run)
    card_numbers = extract_card_numbers(text)
    try:
        cell_numbers = cell_numbers_for(run.get("notebook"))
    except Exception:
        cell_numbers = []
    untraced = match_numbers(card_numbers, cell_numbers)
    return untraced, card_numbers, cell_numbers


def main(argv: list | None = None) -> int:
    """CLI: exit 0 iff zero untraced, 1 on untraced, 2 on usage/lookup error."""
    parser = argparse.ArgumentParser(
        description="Check that every verdict-card number traces to a cell."
    )
    parser.add_argument("run_id", nargs="?", default=None)
    parser.add_argument("--run-id", "--run", dest="run_id_opt", default=None)
    parser.add_argument("--card-text", default=None)
    parser.add_argument("--card-file", default=None)
    args = parser.parse_args(argv)
    run_id = args.run_id_opt or args.run_id
    if not run_id or not str(run_id).strip():
        print("error: missing run id")
        return 2
    try:
        untraced, card_numbers, cell_numbers = check(
            str(run_id).strip(),
            card_text=args.card_text,
            card_file=args.card_file,
        )
    except NotFound as exc:
        print("error: %s" % exc)
        return 2
    except ValueError as exc:
        print("error: %s" % exc)
        return 2
    if not untraced:
        print(
            "0 untraced (%d card numbers checked against %d cell numbers)"
            % (len(card_numbers), len(cell_numbers))
        )
        return 0
    print("untraced: %r" % (untraced,))
    print(
        "%d untraced of %d card numbers (%d cell numbers)"
        % (len(untraced), len(card_numbers), len(cell_numbers))
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
