"""Capped debug loop: traceback to repair, max 3 iterations (issue #16).

Stdlib only (plus existing ``agent.llm`` / ``app.config``): no subprocess,
no network, no new dependencies. Offline (default, ``QED_OFFLINE=1`` or no
``META_API_KEY``) both :func:`repair` and :func:`debug_loop` are fully
deterministic; online each repair makes exactly one ``agent.llm.complete``
call and falls back to the deterministic heuristic on any LLM failure.
"""

import os
import re

from app.config import parse_offline

MAX_ITERATIONS = 3
MAX_CODE_CHARS = 4000
MAX_TRACEBACK_CHARS = 4000
MAX_SPEC_CHARS = 1000

_MISSING_MODULE_RE = re.compile(r"No module named ['\"]([^'\"]+)['\"]")
_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


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


def _spec_label(spec) -> str:
    """Short spec label for prompt context; never raises."""
    try:
        if spec is None:
            return "unknown"
        if isinstance(spec, dict):
            dataset = _coerce_str(spec.get("dataset"), "")
            estimator = _coerce_str(spec.get("estimator"), "")
            label = f"dataset={dataset or 'unknown'} estimator={estimator or 'unknown'}"
            return label[:MAX_SPEC_CHARS] or "unknown"
        text = _coerce_str(spec, "unknown")
        text = text.strip()[:MAX_SPEC_CHARS]
        return text or "unknown"
    except Exception:
        return "unknown"


def _coerce_attempt(attempt) -> int:
    try:
        number = int(attempt)
    except (TypeError, ValueError):
        return 0
    if number < 0:
        return 0
    return number


def build_diagnose_prompt(code, traceback, spec, attempt=0) -> str:
    """Build the repair prompt; never raises on ragged input."""
    try:
        body = _coerce_str(code, "")
        tb = _coerce_str(traceback, "")
        number = _coerce_attempt(attempt)
        label = _spec_label(spec)
        return (
            "Repair the failing Python analysis code below so it runs without error.\n"
            f"Repair attempt {number + 1}.\n"
            f"Spec: {label}\n"
            f"Failing code:\n{body.strip()[:MAX_CODE_CHARS]}\n"
            f"Traceback:\n{tb.strip()[:MAX_TRACEBACK_CHARS]}\n"
            "Return Python code only, no prose."
        )
    except Exception:
        return "Return Python code only, no prose."


def _offline_repair(code, traceback) -> str:
    """Deterministic import-guard / comment heuristic; never raises."""
    try:
        body = _coerce_str(code, "")
        tb = _coerce_str(traceback, "")
        match = _MISSING_MODULE_RE.search(tb)
        if match:
            raw_mod = match.group(1).split(".")[0].strip()
            mod = raw_mod if _IDENTIFIER_RE.fullmatch(raw_mod or "") else None
            if mod:
                guard = (
                    f"try:\n    import {mod}\n"
                    f"except ImportError:\n    {mod} = None  # missing dependency guarded by offline repair\n"
                )
                if body.strip():
                    return guard + body
                return guard + "# original code was empty\n"
        first_line = ""
        try:
            for line in tb.splitlines():
                if line.strip():
                    first_line = line.strip()[:160]
                    break
        except Exception:
            first_line = ""
        hint = f": {first_line}" if first_line else ""
        if body.strip():
            return body + f"\n# repair attempt{hint}\n"
        return f"# repair attempt{hint}\n"
    except Exception:
        try:
            return _coerce_str(code, "") + "\n# repair attempt\n"
        except Exception:
            return "# repair attempt\n"


def _fallback_complete(prompt: str, *args, **kwargs) -> str:
    raise RuntimeError("no LLM client available")


def _resolve_complete(complete_fn):
    if complete_fn is not None:
        return complete_fn
    try:
        from agent.llm import complete as llm_complete
    except ImportError:
        return _fallback_complete
    return llm_complete


def _llm_candidate_valid(candidate, original_code: str) -> bool:
    try:
        if not isinstance(candidate, str) or not candidate.strip():
            return False
        stripped = candidate.strip()
        if stripped == (original_code or "").strip():
            return False
        if "def " not in stripped and "import " not in stripped:
            return False
        return True
    except Exception:
        return False


def repair(code, traceback, spec, attempt=0, complete_fn=None) -> str:
    """Repair failing code given its traceback; never raises on ragged input.

    Offline (``QED_OFFLINE`` unset/empty/truthy, or no ``META_API_KEY`` when
    no ``complete_fn`` is injected) returns the deterministic heuristic.
    Online it makes exactly one LLM call and falls back to the heuristic on
    any failure or invalid (empty / unchanged / no ``def``/``import``) output.
    Invalid input yields a commented passthrough; this function never raises,
    never executes code, and never touches network/subprocess itself.
    """
    try:
        body = _coerce_str(code, "")
        tb = _coerce_str(traceback, "")
        number = _coerce_attempt(attempt)
    except Exception:
        return "# repair attempt: invalid input\n"
    try:
        if parse_offline(os.environ.get("QED_OFFLINE")):
            return _offline_repair(body, tb)
        if complete_fn is None and not os.environ.get("META_API_KEY", "").strip():
            return _offline_repair(body, tb)
        complete = _resolve_complete(complete_fn)
        prompt = build_diagnose_prompt(body, tb, spec, number)
        try:
            candidate = complete(prompt)
        except Exception:
            return _offline_repair(body, tb)
        if _llm_candidate_valid(candidate, body):
            return candidate
        return _offline_repair(body, tb)
    except Exception:
        try:
            return _offline_repair(body, tb)
        except Exception:
            return "# repair attempt\n"


def _failure_artifact(error_log, final_code, attempts) -> dict:
    """Honest exhaustion artifact: empty outputs, never invented numbers."""
    try:
        log = list(error_log) if isinstance(error_log, list) else list(error_log or [])
    except Exception:
        log = []
    try:
        cleaned = [_coerce_str(entry, "unknown error") or "unknown error" for entry in log]
    except Exception:
        cleaned = []
    try:
        count = int(attempts)
    except (TypeError, ValueError):
        count = len(cleaned)
    try:
        final = _coerce_str(final_code, "")
    except Exception:
        final = ""
    return {
        "status": "failed",
        "verdict": "FAILED",
        "fragile_choice": None,
        "outputs": {},
        "error_log": cleaned,
        "attempts": count,
        "final_code": final,
    }


def _coerce_run_result(result):
    """Coerce ``run_fn`` output to ``(ok, outputs, traceback)``; never raises."""
    try:
        if isinstance(result, dict):
            ok = result.get("ok", result.get("success", False))
            outputs = result.get("outputs", {})
            tb = result.get("traceback", result.get("error", ""))
            if not isinstance(outputs, dict):
                outputs = {}
            return bool(ok), dict(outputs), _coerce_str(tb, "")
        if isinstance(result, (tuple, list)):
            if len(result) == 3:
                ok, outputs, tb = result[0], result[1], result[2]
                if not isinstance(outputs, dict):
                    outputs = {}
                return bool(ok), dict(outputs), _coerce_str(tb, "")
            if len(result) == 2:
                ok, outputs = result[0], result[1]
                if not isinstance(outputs, dict):
                    outputs = {}
                return bool(ok), dict(outputs), ""
        return False, {}, _coerce_str(result, "") or "run_fn returned invalid result"
    except Exception:
        return False, {}, "run_fn returned invalid result"


def _coerce_max_iterations(value) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return MAX_ITERATIONS
    if number < 1:
        return 1
    return number


def debug_loop(initial_code, spec, run_fn, repair_fn=None, complete_fn=None, max_iterations=MAX_ITERATIONS) -> dict:
    """Run author -> execute -> repair at most ``max_iterations`` times.

    ``run_fn(code)`` must return an ``(ok, outputs, traceback)`` triple
    (ragged shapes are coerced to failure). On success returns a
    ``complete`` artifact with ``verdict None``; on exhaustion returns the
    honest failure artifact (``failed`` / ``FAILED`` / ``fragile_choice``
    ``None`` / empty ``outputs`` / full ``error_log``). Never raises on
    ragged input; never executes code itself beyond calling ``run_fn``.
    """
    try:
        limit = _coerce_max_iterations(max_iterations)
    except Exception:
        limit = MAX_ITERATIONS
    try:
        code = _coerce_str(initial_code, "")
    except Exception:
        code = ""
    try:
        if not callable(run_fn):
            return _failure_artifact(["run_fn is not callable"], code, 0)
    except Exception:
        return _failure_artifact(["run_fn is not callable"], code, 0)
    error_log: list[str] = []
    try:
        for attempt in range(limit):
            try:
                result = run_fn(code)
            except Exception as exc:
                tb_text = _coerce_str(exc, "") or repr(exc)
                error_log.append(tb_text.strip() or "unknown error")
                if attempt >= limit - 1:
                    break
                try:
                    code = _repair_step(code, error_log[-1], spec, attempt, repair_fn, complete_fn)
                except Exception:
                    code = _offline_repair(code, error_log[-1])
                continue
            ok, outputs, tb_text = _coerce_run_result(result)
            if ok:
                try:
                    clean_outputs = dict(outputs) if isinstance(outputs, dict) else {}
                except Exception:
                    clean_outputs = {}
                return {
                    "status": "complete",
                    "verdict": None,
                    "fragile_choice": None,
                    "outputs": clean_outputs,
                    "code": code,
                    "final_code": code,
                    "attempts": attempt + 1,
                    "error_log": list(error_log),
                }
            error_log.append(tb_text.strip() or "unknown error")
            if attempt >= limit - 1:
                break
            try:
                code = _repair_step(code, error_log[-1], spec, attempt, repair_fn, complete_fn)
            except Exception:
                try:
                    code = _offline_repair(code, error_log[-1])
                except Exception:
                    pass
        return _failure_artifact(error_log, code, limit)
    except Exception:
        try:
            return _failure_artifact(error_log, code, limit)
        except Exception:
            return {
                "status": "failed",
                "verdict": "FAILED",
                "fragile_choice": None,
                "outputs": {},
                "error_log": [],
                "attempts": 0,
                "final_code": "",
            }


def _repair_step(code, traceback, spec, attempt, repair_fn, complete_fn) -> str:
    """Apply one repair step via ``repair_fn`` or :func:`repair`; never raises."""
    try:
        if repair_fn is not None:
            try:
                candidate = repair_fn(code, traceback, spec, attempt)
            except TypeError:
                try:
                    candidate = repair_fn(code, traceback, spec)
                except Exception:
                    return _offline_repair(code, traceback)
            except Exception:
                return _offline_repair(code, traceback)
            if isinstance(candidate, str) and candidate.strip():
                return candidate
            return _offline_repair(code, traceback)
        return repair(code, traceback, spec, attempt, complete_fn=complete_fn)
    except Exception:
        return _offline_repair(code, traceback)
