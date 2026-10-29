"""Offline tests for the capped debug loop (issue #16)."""

from agent import MAX_ITERATIONS, debug_loop, repair
from agent.diagnose import build_diagnose_prompt


def _scrubbed_env(monkeypatch, **overrides):
    for key in ("META_API_KEY", "META_API_URL", "QED_OFFLINE"):
        monkeypatch.delenv(key, raising=False)
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)


FAILING_CODE = "import foo\n\n\ndef analyze(spec=None, dataset_profile=None):\n    return foo.run()\n"
TRACEBACK = "Traceback (most recent call last):\n  File \"a.py\", line 1, in <module>\nModuleNotFoundError: No module named 'foo'"
SPEC = {"dataset": "d", "estimator": "e", "headline_numbers": {"x": 1.0}, "significance_claim": "p < 0.05"}


def test_repair_import_fix_offline(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    fixed = repair(FAILING_CODE, TRACEBACK, SPEC, 0)
    assert isinstance(fixed, str)
    assert fixed != FAILING_CODE
    assert "import foo" in fixed


def test_debug_loop_exhaustion_is_honest_failure(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    calls = []

    def run_fn(code):
        calls.append(code)
        return (False, {}, "Traceback: boom %d" % len(calls))

    result = debug_loop(FAILING_CODE, SPEC, run_fn)
    assert len(calls) == 3
    assert MAX_ITERATIONS == 3
    assert result["status"] in ("failed", "complete")
    assert result["verdict"] == "FAILED"
    assert result["fragile_choice"] is None
    assert result["outputs"] == {}
    assert len(result["error_log"]) == 3


def test_debug_loop_retry_success(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    state = {"n": 0}

    def run_fn(code):
        state["n"] += 1
        if state["n"] < 2:
            return (False, {}, "Traceback: first failure")
        return (True, {"estimate": 1.0}, "")

    result = debug_loop(FAILING_CODE, SPEC, run_fn)
    assert result["status"] == "complete"
    assert result["verdict"] is None
    assert result["outputs"] == {"estimate": 1.0}
    assert result["attempts"] == 2


def test_offline_makes_zero_llm_calls(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")

    def stub(prompt):
        raise AssertionError("LLM must not be called offline")

    fixed = repair(FAILING_CODE, TRACEBACK, SPEC, 0, complete_fn=stub)
    assert fixed != FAILING_CODE

    def run_fn(code):
        return (False, {}, "Traceback: boom")

    result = debug_loop(FAILING_CODE, SPEC, run_fn, complete_fn=stub)
    assert result["status"] == "failed"
    assert result["outputs"] == {}


def test_ragged_inputs_never_raise(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    assert isinstance(repair(None, None, None), str)
    assert isinstance(repair(123, 456, 789, "x"), str)
    assert isinstance(build_diagnose_prompt(None, None, None), str)
    assert isinstance(repair("", "", SPEC, 0), str)
    result = debug_loop(None, None, "not-callable")
    assert result["status"] == "failed"
    assert result["verdict"] == "FAILED"
    assert result["fragile_choice"] is None
    assert result["outputs"] == {}

    def weird_run(code):
        return "garbage"

    result = debug_loop(FAILING_CODE, SPEC, weird_run, max_iterations=2)
    assert result["status"] == "failed"
    assert result["outputs"] == {}
