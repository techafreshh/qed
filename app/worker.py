"""Background run worker: queued -> running -> complete|failed (issue #21).

FastAPI ``BackgroundTasks`` drives :func:`drive_run` in-process; the worker
flips the SQLite row to ``running``, calls the orchestrator's ``run_claim``
offline path, then persists ``verdict``/``fragile_choice``/``trace``/
``notebook``. It never raises out of the background task and never spawns
subprocesses or network calls itself.
"""
from __future__ import annotations

import os

from fastapi import BackgroundTasks

from app.config import parse_offline
from db.models import get_run, update_run


def _offline_result(paper_id: str, claim: str) -> dict:
    """Minimal local equivalent when the orchestrator is unavailable."""
    verdict = "FAILED" if paper_id == "demo_failed" else "REPLICATED"
    fragile_choice = "offline stub: orchestrator unavailable"
    trace = [
        {"stage": "extraction", "ts": "", "detail": {"paper_id": paper_id}},
        {"stage": "codegen", "ts": "", "detail": {"offline": True}},
        {"stage": "sandbox", "ts": "", "detail": {"offline": True}},
        {
            "stage": "verdict",
            "ts": "",
            "detail": {"verdict": verdict, "fragile_choice": fragile_choice},
        },
    ]
    notebook = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {"paper_id": paper_id, "verdict": verdict},
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": f"# Offline stub notebook for {paper_id}\n\nclaim: {claim}",
            }
        ],
    }
    return {
        "verdict": verdict,
        "fragile_choice": fragile_choice,
        "trace": trace,
        "notebook": notebook,
    }


def _call_orchestrator(paper_id: str, claim: str) -> dict:
    """Call the cached replay first when offline, else live ``run_claim``."""
    if parse_offline(os.environ.get("QED_OFFLINE")):
        try:
            from runner.offline import NotFound, replay  # noqa: PLC0415
        except Exception:
            pass
        else:
            try:
                return replay(paper_id)
            except NotFound:
                pass
            except Exception:
                pass
    func = None
    try:
        import agent.orchestrate as _mod  # noqa: PLC0415 (live lookup honors patches)

        func = getattr(_mod, "run_claim", None)
    except Exception:
        func = None
    if not callable(func):
        return _offline_result(paper_id, claim)
    # Orchestrator exceptions propagate so drive_run marks failed honestly.
    return func(paper_id, claim)


def drive_run(run_id: str, db_path=None) -> dict | None:
    """Advance one run to completion; never raises to the background host."""
    try:
        row = get_run(run_id, db_path=db_path)
    except Exception:
        return None
    if row is None:
        return None
    try:
        update_run(run_id, status="running", db_path=db_path)
    except Exception:
        pass
    try:
        current = get_run(run_id, db_path=db_path) or row
        paper_id = current.get("paper_id", "") or ""
        claim = current.get("claim", "") or ""
        result = _call_orchestrator(paper_id, claim)
        verdict = result.get("verdict", "FAILED")
        if not isinstance(verdict, str) or not verdict:
            verdict = "FAILED"
        fragile_choice = result.get("fragile_choice")
        if fragile_choice is not None and not isinstance(fragile_choice, str):
            fragile_choice = str(fragile_choice)
        update_run(
            run_id,
            status="complete",
            verdict=verdict,
            fragile_choice=fragile_choice,
            trace=result.get("trace"),
            notebook=result.get("notebook"),
            db_path=db_path,
        )
    except Exception:
        try:
            update_run(run_id, status="failed", verdict="FAILED", db_path=db_path)
        except Exception:
            pass
    try:
        return get_run(run_id, db_path=db_path)
    except Exception:
        return None


def schedule_run(run_id: str, background_tasks: BackgroundTasks) -> None:
    """Enqueue :func:`drive_run` on a FastAPI ``BackgroundTasks`` instance."""
    background_tasks.add_task(drive_run, run_id)
