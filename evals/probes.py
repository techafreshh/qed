"""Adversarial honest-refusal probes (issue #27).

Four credential-free probes proving the system refuses or degrades
honestly instead of fabricating verdict numbers: a missing input file,
an underspecified claim, an excluded (banned-import) dependency, and an
over-timebox run. Each probe returns ``{"name", "outcome", "reason"}``
with ``outcome`` in ``{"refused", "degraded"}`` and a non-empty reason,
and never raises. The ``--offline`` CLI prints one ``PASS`` line per
probe and exits 0 iff all four refuse/degrade honestly.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

PROBE_NAMES = (
    "missing_file",
    "underspecified_claim",
    "excluded_dependency",
    "overtime_run",
)

_MISSING_PAPER_ID = "no_such_paper_missing_file_probe"
_VAGUE_CLAIM = "it works"
_BANNED_CODE = "import stata\nresult = stata.run('model')\nprint(result)\n"


def probe_missing_file() -> dict:
    """Missing fixture must refuse via NotFound, emitting no verdict numbers."""
    name = "missing_file"
    try:
        from agent.validate import Refused, check_missing_file
        from runner.offline import NotFound, replay
    except Exception as exc:
        return {"name": name, "outcome": "error",
                "reason": "probe setup failed: %s" % exc}
    try:
        try:
            replay(_MISSING_PAPER_ID)
            return {"name": name, "outcome": "error",
                    "reason": "replay unexpectedly succeeded for a missing "
                              "fixture; refusing to emit a verdict"}
        except NotFound:
            pass
        try:
            check_missing_file(_MISSING_PAPER_ID, exists=False)
        except Refused:
            pass
        else:
            return {"name": name, "outcome": "error",
                    "reason": "missing-file check did not refuse; refusing "
                              "to emit a verdict"}
        return {"name": name, "outcome": "refused",
                "reason": "missing input file refused honestly: unknown "
                          "paper; no verdict emitted"}
    except Exception as exc:  # noqa: BLE001 - probes never raise
        return {"name": name, "outcome": "error",
                "reason": "probe failed: %s" % exc}


def probe_underspecified_claim() -> dict:
    """Vague claim POST must 422, never 500 and never a queued verdict."""
    name = "underspecified_claim"
    try:
        from fastapi.testclient import TestClient

        from app.main import app
    except Exception as exc:
        return {"name": name, "outcome": "error",
                "reason": "probe setup failed: %s" % exc}
    try:
        client = TestClient(app)
        response = client.post(
            "/api/runs",
            json={"paper_id": "demo_replicated", "claim": _VAGUE_CLAIM},
        )
        if response.status_code == 422:
            return {"name": name, "outcome": "refused",
                    "reason": "underspecified claim rejected with 422; "
                              "no run queued and no verdict emitted"}
        return {"name": name, "outcome": "error",
                "reason": "expected 422 for underspecified claim, got %s; "
                          "refusing to emit a verdict" % response.status_code}
    except Exception as exc:  # noqa: BLE001 - probes never raise
        return {"name": name, "outcome": "error",
                "reason": "probe failed: %s" % exc}


def probe_excluded_dependency() -> dict:
    """Banned-import codegen output must refuse before any sandbox verdict."""
    name = "excluded_dependency"
    try:
        from agent.validate import Refused, check_banned_imports
    except Exception as exc:
        return {"name": name, "outcome": "error",
                "reason": "probe setup failed: %s" % exc}
    try:
        try:
            check_banned_imports(_BANNED_CODE)
        except Refused as exc:
            static_reason = exc.reason
        else:
            return {"name": name, "outcome": "error",
                    "reason": "banned import passed the static scan; "
                              "refusing to emit a verdict"}
        from agent.orchestrate import run_claim

        class _BannedBackend:
            def author(self, spec, dataset_profile, prior_traceback=None):
                return _BANNED_CODE

        result = run_claim(
            "demo_replicated",
            "wages rise with the minimum wage",
            backend=_BannedBackend(),
        )
        if result.get("verdict"):
            return {"name": name, "outcome": "error",
                    "reason": "orchestrator emitted a verdict for banned "
                              "code; refusing to emit a verdict"}
        fragile = result.get("fragile_choice") or ""
        if "refused" not in str(fragile).lower():
            return {"name": name, "outcome": "error",
                    "reason": "orchestrator did not name the refusal; "
                              "refusing to emit a verdict"}
        return {"name": name, "outcome": "refused",
                "reason": "excluded dependency refused honestly: %s"
                % static_reason}
    except Exception as exc:  # noqa: BLE001 - probes never raise
        return {"name": name, "outcome": "error",
                "reason": "probe failed: %s" % exc}


def probe_overtime_run() -> dict:
    """Over-timebox execution must hard-kill and degrade, never fake output."""
    name = "overtime_run"
    try:
        from runner.sandbox import TIMEOUT_EXIT_CODE, run_code
    except Exception as exc:
        return {"name": name, "outcome": "error",
                "reason": "probe setup failed: %s" % exc}
    try:
        result = run_code("import time; time.sleep(5)", timebox=0.2)
        if result.exit_code == TIMEOUT_EXIT_CODE and "hard kill" in (
            result.stderr or ""
        ):
            return {"name": name, "outcome": "degraded",
                    "reason": "over-timebox run hard-killed honestly; "
                              "timeout surfaced instead of a verdict"}
        return {"name": name, "outcome": "error",
                "reason": "expected an honest timeout with no output; "
                          "refusing to emit a verdict"}
    except Exception as exc:  # noqa: BLE001 - probes never raise
        return {"name": name, "outcome": "error",
                "reason": "probe failed: %s" % exc}


_PROBES = (
    probe_missing_file,
    probe_underspecified_claim,
    probe_excluded_dependency,
    probe_overtime_run,
)


def run_all() -> list[dict]:
    """Run all four probes in fixed order; never raises."""
    results = []
    for probe in _PROBES:
        try:
            result = probe()
        except Exception as exc:  # noqa: BLE001 - belt and braces
            result = {"name": getattr(probe, "__name__", "probe"),
                      "outcome": "error",
                      "reason": "probe crashed: %s" % exc}
        if not isinstance(result, dict):
            result = {"name": getattr(probe, "__name__", "probe"),
                      "outcome": "error", "reason": "probe misbehaved"}
        results.append(result)
    return results


def main(argv: list[str] | None = None) -> int:
    """CLI: force offline, print one PASS/FAIL line per probe."""
    parser = argparse.ArgumentParser(
        description="Run the four honest-refusal adversarial probes offline."
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run the credential-free offline probes (acceptance mode).",
    )
    parser.parse_args(argv)
    os.environ["QED_OFFLINE"] = "1"
    ok = True
    for result in run_all():
        name = result.get("name") or "probe"
        outcome = result.get("outcome") or "error"
        reason = result.get("reason") or ""
        passed = outcome in ("refused", "degraded") and bool(str(reason).strip())
        if not passed:
            ok = False
        print("%s: %s (%s: %s)"
              % (name, "PASS" if passed else "FAIL", outcome, reason))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
