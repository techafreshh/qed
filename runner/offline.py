"""Offline cached-run replay runner (issue #15).

Loads versioned fixtures from ``library/cache/<id>/`` with no network,
no subprocess, and no model calls. Used automatically when
``QED_OFFLINE=1``; unknown or corrupt fixtures raise :class:`NotFound`
so callers can map it to a 404.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path

from app.config import parse_offline
from rubric.verdict import FAILED, PARTIAL, REPLICATED

_VALID_VERDICTS = frozenset({REPLICATED, PARTIAL, FAILED})

CACHE_ROOT = Path(__file__).resolve().parent.parent / "library" / "cache"


class NotFound(Exception):
    """Raised when no usable cached run exists for a paper id."""


def is_offline() -> bool:
    """True when the offline replay path should be used (``QED_OFFLINE=1``)."""
    return parse_offline(os.environ.get("QED_OFFLINE"))


def _check_id(paper_id: str) -> str:
    if not isinstance(paper_id, str):
        raise NotFound("unknown paper %r" % (paper_id,))
    cleaned = paper_id.strip()
    if not cleaned:
        raise NotFound("unknown paper %r" % (paper_id,))
    for bad in ("/", "\\", "."):
        if bad in cleaned:
            raise NotFound("unknown paper %r" % (paper_id,))
    if "\x00" in cleaned:
        raise NotFound("unknown paper %r" % (paper_id,))
    return cleaned


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise NotFound("unreadable fixture %s" % path.name) from exc


def _check_trace(trace) -> list:
    if not isinstance(trace, list) or not trace:
        raise NotFound("fixture trace must be a non-empty list")
    for entry in trace:
        if not isinstance(entry, dict):
            raise NotFound("fixture trace entries must be dicts")
        stage = entry.get("stage")
        if not isinstance(stage, str) or not stage.strip():
            raise NotFound("fixture trace entry missing stage")
        if not isinstance(entry.get("ts"), str):
            raise NotFound("fixture trace entry missing ts")
        if not isinstance(entry.get("detail"), dict):
            raise NotFound("fixture trace entry missing detail")
    return trace


def replay(paper_id: str) -> dict:
    """Return the cached ``{notebook, verdict, trace, fragile_choice}`` run.

    Raises :class:`NotFound` for unknown ids, path-traversal attempts,
    and missing or invalid fixture files.
    """
    cleaned = _check_id(paper_id)
    directory = CACHE_ROOT / cleaned
    try:
        is_dir = directory.is_dir()
    except OSError as exc:
        raise NotFound("unknown paper %r" % (paper_id,)) from exc
    if not is_dir:
        raise NotFound("unknown paper %r" % (paper_id,))
    try:
        version = (directory / "VERSION").read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise NotFound("fixture %r missing VERSION" % cleaned) from exc
    if not version:
        raise NotFound("fixture %r has empty VERSION" % cleaned)
    notebook = _read_json(directory / "notebook.json")
    if not isinstance(notebook, dict):
        raise NotFound("fixture %r notebook must be a dict" % cleaned)
    cells = notebook.get("cells")
    if not isinstance(cells, list) or len(cells) < 1:
        raise NotFound("fixture %r notebook must have cells" % cleaned)
    result = _read_json(directory / "result.json")
    if not isinstance(result, dict):
        raise NotFound("fixture %r result must be a dict" % cleaned)
    verdict = result.get("verdict")
    if verdict not in _VALID_VERDICTS:
        raise NotFound("fixture %r has invalid verdict" % cleaned)
    fragile_choice = result.get("fragile_choice")
    if not isinstance(fragile_choice, str) or not fragile_choice.strip():
        raise NotFound("fixture %r missing fragile_choice" % cleaned)
    trace = _check_trace(result.get("trace"))
    return copy.deepcopy(
        {
            "notebook": notebook,
            "verdict": verdict,
            "trace": trace,
            "fragile_choice": fragile_choice,
        }
    )
