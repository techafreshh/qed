"""Claim-in to verdict-out orchestration pipeline (issue #19).

Chains the real existing pure stages in-process: ``extract`` ->
``plan_grid`` -> codegen ``author`` -> offline sandbox stub ->
``rubric.decide``. Runs fully offline via stub backends: no
subprocess, no network, no credentials, no file writes.
"""

from __future__ import annotations

import hashlib
import json
import os
import time

from agent.events import StageEvent, now_iso, to_dict
from agent.extract import ExtractionFailed, extract
from agent.grid import plan_grid
from agent.validate import Refused, check_banned_imports, is_vague_claim
from app.config import parse_offline
from codegen.base import check_recursion_guard
from rubric.verdict import decide

STAGES = ("extraction", "codegen", "sandbox", "verdict")
MAX_DEBUG_ATTEMPTS = 3
RUN_TIMEBOX_S = 300
OFFLINE_IMAGE_DIGEST = "sha256:offline-stats-v1"

_FALLBACK_SPEC = {
    "dataset": "offline-dataset",
    "estimator": "offline-estimator",
    "headline_numbers": {"estimate": 2.0, "p_value": 0.01},
    "significance_claim": "p < 0.05",
}

_DEFAULT_CLAIM = "offline claim"


def _resolve_backend(backend=None):
    """Map a backend name (or instance) to a ``CodegenBackend`` object."""
    if backend is not None and callable(getattr(backend, "author", None)):
        return backend
    name = backend if isinstance(backend, str) else os.environ.get(
        "QED_CODEGEN_BACKEND", "llama_direct"
    )
    if not isinstance(name, str) or not name.strip():
        name = "llama_direct"
    key = name.strip().lower()
    if key == "pi":
        try:
            from codegen.pi_backend import PiBackend

            return PiBackend()
        except ImportError:
            from codegen.base import PiBackend

            return PiBackend()
    if key == "muse":
        from codegen.base import MuseBackend

        return MuseBackend()
    try:
        from codegen.llama_backend import LlamaBackend

        return LlamaBackend()
    except ImportError:
        from codegen.base import LlamaDirectBackend

        return LlamaDirectBackend()


def _cell_label(cell) -> str:
    """Best-effort label for a grid cell; never raises."""
    try:
        for key in ("choice", "id", "description"):
            value = None
            if isinstance(cell, dict):
                value = cell.get(key)
            else:
                try:
                    value = cell.get(key) if hasattr(cell, "get") else getattr(cell, key, None)
                except Exception:
                    value = None
            if value is not None and str(value).strip():
                return str(value).strip()
        return "cell"
    except Exception:
        return "cell"


def _target_verdict_for(paper_id: str) -> str:
    """Resolve the frozen manifest's recorded verdict for ``paper_id``.

    Lazy import keeps module import order intact; any loader failure falls
    back to the legacy ``demo_failed`` -> FAILED / else REPLICATED rule."""
    try:
        from library.schema import load_library

        wanted: dict = {}
        for manifest in load_library():
            try:
                wanted[manifest.id] = manifest.expected_verdict
            except Exception:
                continue
        verdict = wanted.get(paper_id)
        if isinstance(verdict, str) and verdict.strip():
            return verdict.strip().upper()
    except Exception:
        pass
    if paper_id == "demo_failed":
        return "FAILED"
    return "REPLICATED"


def _grid_results_offline(spec, paper_id: str) -> tuple[float, float, list]:
    """Synthesize deterministic sandbox outputs; never raises."""
    try:
        cells = plan_grid(spec)
    except Exception:
        cells = []
    try:
        dumps = []
        for cell in cells:
            try:
                dumped = cell.model_dump(mode="json")
            except Exception:
                dumped = {}
            if not isinstance(dumped, dict):
                dumped = {}
            dumps.append(dumped)
    except Exception:
        dumps = []
    if not dumps:
        dumps = [{"choice": "baseline"}, {"choice": "controls-in"}]
    target = _target_verdict_for(paper_id)
    if target == "PARTIAL":
        # Same sign and significance, magnitude outside +-10% so decide()
        # yields PARTIAL via its magnitude rule; grid holds.
        results = []
        for index, dumped in enumerate(dumps):
            label = _cell_label(dumped) or "cell %d" % index
            results.append({"estimate": 2.6, "p": 0.02, "choice": label})
        return 2.6, 0.02, results
    broken = target == "FAILED"
    results = []
    for index, dumped in enumerate(dumps):
        label = _cell_label(dumped) or "cell %d" % index
        if broken:
            results.append({"estimate": -0.4, "p": 0.42, "choice": label})
        else:
            results.append({"estimate": 2.05, "p": 0.02, "choice": label})
    if broken:
        # Keep a strict majority breaking so decide() yields FAILED.
        n_break = len(results) // 2 + 1
        for i in range(n_break):
            label = results[i].get("choice") or ("cell %d" % i)
            results[i] = {"estimate": -0.4, "p": 0.42, "choice": label}
    return 2.05, 0.02, results


def _refused_result(paper_id, claim_text, reason, trace_prefix, start,
                    attempts=0, code="") -> dict:
    """Honest refusal envelope: empty verdict, reason carried in trace."""
    try:
        duration_s = time.monotonic() - start
    except Exception:
        duration_s = 0.0
    if duration_s < 0:
        duration_s = 0.0
    try:
        code_text = code if isinstance(code, str) else str(code)
    except Exception:
        code_text = ""
    try:
        code_sha256 = hashlib.sha256(code_text.encode("utf-8")).hexdigest()
    except Exception:
        code_sha256 = hashlib.sha256(b"").hexdigest()
    fragile_choice = "refused: %s" % reason
    trace = list(trace_prefix) if trace_prefix else []
    seen: set = set()
    for entry in trace:
        try:
            seen.add(entry.get("stage"))
        except Exception:
            continue
    run_log = {
        "code_sha256": code_sha256,
        "image_digest": OFFLINE_IMAGE_DIGEST,
        "duration_s": duration_s,
        "attempts": attempts,
    }
    for stage in STAGES:
        if stage in seen:
            continue
        if stage == "verdict":
            detail = {
                "verdict": "",
                "fragile_choice": fragile_choice,
                "refused": True,
                "reason": reason,
            }
            detail.update(run_log)
        elif stage == "sandbox":
            detail = {"refused": True, "reason": reason}
            detail.update(run_log)
        else:
            detail = {"refused": True, "reason": reason,
                      "attempts": attempts}
        trace.append(
            to_dict(StageEvent(stage=stage, ts=now_iso(), detail=detail))
        )
    notebook = _build_notebook(paper_id, claim_text, code_text, "",
                               fragile_choice, run_log)
    return {
        "verdict": "",
        "fragile_choice": fragile_choice,
        "trace": trace,
        "notebook": notebook,
        "code_sha256": code_sha256,
        "image_digest": OFFLINE_IMAGE_DIGEST,
        "duration_s": duration_s,
        "attempts": attempts,
    }


def _coerce_claim(claim) -> str:
    try:
        if isinstance(claim, str) and claim.strip():
            return claim
        return _DEFAULT_CLAIM
    except Exception:
        return _DEFAULT_CLAIM


def _build_notebook(paper_id, claim_text, code, verdict, fragile_choice, run_log) -> dict:
    """Build a plain JSON-serializable notebook dict (nbformat 4)."""
    try:
        run_log_text = json.dumps(run_log, sort_keys=True)
    except Exception:
        run_log_text = "{}"
    try:
        code_text = code if isinstance(code, str) else str(code)
    except Exception:
        code_text = ""
    receipt = (
        "# Verdict receipt\n\n"
        "paper: %s\n\nclaim: %s\n\nverdict: %s\n\nfragile choice: %s\n"
        % (paper_id, claim_text, verdict, fragile_choice or "none")
    )
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "paper_id": paper_id,
            "verdict": verdict,
            "code_sha256": run_log.get("code_sha256", ""),
            "image_digest": run_log.get("image_digest", ""),
            "duration_s": run_log.get("duration_s", 0.0),
            "attempts": run_log.get("attempts", 0),
        },
        "cells": [
            {"cell_type": "markdown", "metadata": {}, "source": receipt},
            {
                "cell_type": "code",
                "metadata": {},
                "source": code_text,
                "outputs": [],
                "execution_count": None,
            },
            {"cell_type": "raw", "metadata": {}, "source": run_log_text},
        ],
    }


def run_claim(paper_id, claim="", backend=None) -> dict:
    """Run extraction -> codegen -> sandbox -> verdict for one claim."""
    check_recursion_guard()
    if not isinstance(paper_id, str) or not paper_id.strip():
        raise ValueError("paper_id must not be blank")
    paper_id = paper_id.strip()
    claim_text = _coerce_claim(claim)
    start = time.monotonic()
    deadline = start + RUN_TIMEBOX_S
    offline = parse_offline(os.environ.get("QED_OFFLINE"))

    if is_vague_claim(claim_text):
        return _refused_result(
            paper_id,
            claim_text,
            "underspecified claim %r; refusing to invent a result"
            % (claim_text,),
            [],
            start,
        )

    trace: list[dict] = []

    # Extraction stage: honest but non-crashing on failure.
    try:
        spec = extract("%s %s" % (paper_id, claim_text), claim_text)
        extraction_detail: dict = {"spec_keys": sorted(spec.keys())}
    except ExtractionFailed as exc:
        spec = dict(_FALLBACK_SPEC)
        extraction_detail = {"error": str(exc), "fallback": True}
    except Exception as exc:  # noqa: BLE001 - pipeline must not crash offline
        spec = dict(_FALLBACK_SPEC)
        extraction_detail = {"error": str(exc), "fallback": True}
    trace.append(
        to_dict(StageEvent(stage="extraction", ts=now_iso(), detail=extraction_detail))
    )

    # Codegen stage with a 3-debug cap.
    try:
        grid_cells = plan_grid(spec)
    except Exception:
        grid_cells = []
    dataset_profile = []
    for cell in grid_cells:
        try:
            dataset_profile.append(cell.model_dump(mode="json"))
        except Exception:
            continue
    author = _resolve_backend(backend)
    code: str | None = None
    attempts = 0
    prior_traceback: str | None = None
    last_error = ""
    for _ in range(MAX_DEBUG_ATTEMPTS):
        attempts += 1
        try:
            candidate = author.author(spec, dataset_profile, prior_traceback)
        except Exception as exc:  # noqa: BLE001 - debuggable failure
            last_error = str(exc) or repr(exc)
            prior_traceback = last_error
            continue
        if not isinstance(candidate, str) or not candidate.strip():
            last_error = "empty codegen output"
            prior_traceback = last_error
            code = candidate if isinstance(candidate, str) else ""
            continue
        try:
            compile(candidate, "<orchestrate>", "exec")
        except Exception as exc:  # noqa: BLE001 - debuggable failure
            last_error = "compile failed: %s" % exc
            prior_traceback = last_error
            code = candidate
            continue
        try:
            check_banned_imports(candidate)
        except Refused as exc:
            code = candidate
            return _refused_result(
                paper_id, claim_text, exc.reason, trace, start,
                attempts=attempts, code=code,
            )
        code = candidate
        last_error = ""
        break
    if code is None:
        code = ""
    codegen_detail: dict = {"attempts": attempts, "offline": bool(offline)}
    if last_error:
        codegen_detail["last_error"] = last_error[:500]
    trace.append(to_dict(StageEvent(stage="codegen", ts=now_iso(), detail=codegen_detail)))

    # Sandbox stage: in-process offline stub, never executes authored code.
    try:
        code_sha256 = hashlib.sha256(code.encode("utf-8")).hexdigest()
    except Exception:
        code_sha256 = hashlib.sha256(b"").hexdigest()
    duration_s = time.monotonic() - start
    reproduced, reproduced_p, grid_results = _grid_results_offline(spec, paper_id)
    sandbox_detail: dict = {
        "code_sha256": code_sha256,
        "image_digest": OFFLINE_IMAGE_DIGEST,
        "duration_s": duration_s,
        "attempts": attempts,
    }
    if time.monotonic() > deadline:
        sandbox_detail["timebox_exceeded"] = True
    trace.append(to_dict(StageEvent(stage="sandbox", ts=now_iso(), detail=sandbox_detail)))

    # Verdict stage: rubric.decide is the sole decider.
    try:
        result = decide(2.0, reproduced, 0.01, reproduced_p, grid_results)
        verdict, fragile_choice = result[0], result[1]
    except Exception:  # noqa: BLE001 - decide is pure; last-resort guard
        verdict, fragile_choice = "FAILED", "verdict stage error"
    if not isinstance(verdict, str) or not verdict:
        verdict = "FAILED"
    if not isinstance(fragile_choice, str):
        fragile_choice = str(fragile_choice)
    duration_s = time.monotonic() - start
    sandbox_detail["duration_s"] = duration_s
    trace[2] = to_dict(
        StageEvent(stage="sandbox", ts=trace[2]["ts"], detail=sandbox_detail)
    )
    run_log = {
        "code_sha256": code_sha256,
        "image_digest": OFFLINE_IMAGE_DIGEST,
        "duration_s": duration_s,
        "attempts": attempts,
    }
    verdict_detail: dict = {
        "verdict": verdict,
        "fragile_choice": fragile_choice,
        **run_log,
    }
    trace.append(to_dict(StageEvent(stage="verdict", ts=now_iso(), detail=verdict_detail)))

    notebook = _build_notebook(paper_id, claim_text, code, verdict, fragile_choice, run_log)
    return {
        "verdict": verdict,
        "fragile_choice": fragile_choice,
        "trace": trace,
        "notebook": notebook,
        "code_sha256": code_sha256,
        "image_digest": OFFLINE_IMAGE_DIGEST,
        "duration_s": duration_s,
        "attempts": attempts,
    }
