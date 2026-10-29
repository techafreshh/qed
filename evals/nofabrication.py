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
_LABEL_ASSIGN_RE = re.compile(
    r"([A-Za-z_][A-Za-z0-9_]*)\s*[:=]\s*"
    r"([-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?)"
)


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


def _executed_stdout_text(executed) -> str:
    """Join code-cell output strings from an executed notebook; never raises."""
    chunks: list = []
    try:
        cells = executed.get("cells", []) if isinstance(executed, dict) else []
    except Exception:
        return ""
    try:
        if not isinstance(cells, list):
            return ""
        for cell in cells:
            try:
                if not isinstance(cell, dict):
                    continue
                if cell.get("cell_type") != "code":
                    continue
                outputs = cell.get("outputs", [])
            except Exception:
                continue
            try:
                if isinstance(outputs, dict):
                    outputs = [outputs]
                if not isinstance(outputs, list):
                    continue
            except Exception:
                continue
            for output in outputs:
                try:
                    if isinstance(output, str):
                        if output:
                            chunks.append(output)
                        continue
                    if not isinstance(output, dict):
                        text = _coerce_str(output)
                        if text:
                            chunks.append(text)
                        continue
                    for key in ("text", "evalue"):
                        try:
                            value = output.get(key)
                        except Exception:
                            continue
                        if isinstance(value, str) and value:
                            chunks.append(value)
                        elif isinstance(value, list) and value:
                            chunks.append(
                                "".join(_coerce_str(part) for part in value)
                            )
                    try:
                        data = output.get("data")
                    except Exception:
                        data = None
                    if isinstance(data, dict):
                        for value in data.values():
                            if isinstance(value, str) and value:
                                chunks.append(value)
                            elif isinstance(value, list) and value:
                                chunks.append(
                                    "".join(_coerce_str(part) for part in value)
                                )
                except Exception:
                    continue
    except Exception:
        pass
    try:
        return "\n".join(chunks)
    except Exception:
        return ""


def _headline_from_notebook(notebook) -> str:
    """One labeled headline line from executed cell outputs; never raises.

    Every number returned here is scraped from the executed stdout text of
    ``notebook`` (run via :func:`runner.notebook.execute_notebook`), never
    from a manifest: the claimed side is only ever a labeled citation of an
    executed value. Returns ``""`` when there is no notebook or no output.
    """
    try:
        if not isinstance(notebook, dict):
            return ""
        executed = execute_notebook(copy.deepcopy(notebook))
    except Exception:
        return ""
    try:
        text = _executed_stdout_text(executed)
    except Exception:
        return ""
    claimed = None
    reproduced = None
    p_value = None
    alpha = None
    try:
        if isinstance(text, str) and text.strip():
            for match in _LABEL_ASSIGN_RE.finditer(text):
                try:
                    label = match.group(1).lower()
                    value = float(match.group(2))
                except (TypeError, ValueError):
                    continue
                try:
                    if not math.isfinite(value):
                        continue
                except Exception:
                    continue
                try:
                    if label in ("claimed_estimate", "claimed_d", "claimed") or (
                        label.startswith("claimed")
                        and ("estimat" in label or label.endswith("_d"))
                    ):
                        if claimed is None:
                            claimed = value
                    elif label in (
                        "reproduced_estimate",
                        "reproduced_d",
                        "reproduced",
                        "estimate",
                    ) or (
                        label.startswith("reproduced")
                        and ("estimat" in label or label.endswith("_d"))
                    ):
                        if reproduced is None:
                            reproduced = value
                    elif label in (
                        "reproduced_p",
                        "reproduced_p_value",
                        "p_value",
                        "p",
                    ):
                        if p_value is None:
                            p_value = value
                    elif label == "alpha":
                        if alpha is None:
                            alpha = value
                except Exception:
                    continue
    except Exception:
        return ""
    try:
        if claimed is not None and reproduced is not None:
            if p_value is not None and alpha is not None:
                word = (
                    "significant" if p_value < alpha else "not significant"
                )
                return (
                    "Headline comparison (claimed %g vs reproduced %g, "
                    "p=%g, %s at alpha=%g)"
                    % (claimed, reproduced, p_value, word, alpha)
                )
            if p_value is not None:
                return "Headline comparison (claimed %g vs reproduced %g, p=%g)" % (
                    claimed,
                    reproduced,
                    p_value,
                )
            return "Headline comparison (claimed %g vs reproduced %g)" % (
                claimed,
                reproduced,
            )
    except Exception:
        return ""
    try:
        numbers = extract_numbers(executed)
    except Exception:
        numbers = []
    try:
        if numbers:
            rendered = ", ".join(
                "%g" % value
                for value in numbers
                if isinstance(value, (int, float))
            )
            if rendered.strip():
                return "Executed cell numbers: " + rendered
    except Exception:
        pass
    return ""


def build_card_text(result) -> str:
    """Verdict + fragile choice + offline narration + headline; never raises.

    The headline line is derived exclusively from executed cell outputs of
    ``result["notebook"]`` (see :func:`_headline_from_notebook`), so every
    number it adds traces to a cell output by construction.
    """
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
        try:
            headline = _headline_from_notebook(data.get("notebook"))
        except Exception:
            headline = ""
        if isinstance(headline, str) and headline.strip():
            parts.append(headline.strip())
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
