"""Notebook builder: generate and execute a receipt notebook (issue #18).

Builds a real nbformat-v4 notebook from generated analysis code plus
spec-grid cells, executes it (``nbclient`` live, fake executor when
``QED_OFFLINE=1``), and returns executed notebook JSON with cell outputs
plus the numbers extracted from them. Every number on the verdict card
traces to an executed cell output.

Stdlib only at import time: ``nbformat``/``nbclient`` are lazily probed
and the module imports (with a hand-built dict fallback) when absent.
Analysis code never runs in-process; the offline path replays each code
cell in an isolated ``sys.executable -c`` subprocess with a hard timeout.
"""

from __future__ import annotations

import copy
import math
import os
import re
import subprocess
import sys
import uuid
from typing import Any

from app.config import parse_offline

MAX_GRID_CELLS = 8
DEFAULT_TIMEOUT_S = 60.0
MAX_TIMEOUT_S = 300.0

_NUMBER_RE = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?")


def _coerce_str(value: Any, default: str = "") -> str:
    """Best-effort string coercion; never raises."""
    try:
        if value is None:
            return default
        if isinstance(value, str):
            return value
        return str(value)
    except Exception:
        return default


def _coerce_to_dict(spec: Any) -> dict:
    """Best-effort coercion of a spec to a plain dict; never raises."""
    try:
        if spec is None:
            return {}
        if isinstance(spec, dict):
            return dict(spec)
        dump = getattr(spec, "model_dump", None)
        if callable(dump):
            try:
                data = dump()
            except TypeError:
                data = dump(mode="json")
            if isinstance(data, dict):
                return dict(data)
            return {}
        return {}
    except Exception:
        return {}


def _new_id() -> str:
    """Unique hex cell id (nbformat >= 4.5 requires ids to validate)."""
    try:
        return uuid.uuid4().hex[:8]
    except Exception:
        return "cell-%s" % (os.getpid(),)


def _grid_cell_text(entry: Any, index: int) -> str:
    """Render one grid entry as markdown; never raises on ragged input."""
    try:
        if entry is None:
            return "### Grid cell %d\n\n(no description)" % (index + 1,)
        if isinstance(entry, str):
            text = entry.strip()
            return text if text else "### Grid cell %d\n\n(no description)" % (
                index + 1,)
        data = _coerce_to_dict(entry)
        if not data:
            text = _coerce_str(entry, "").strip()
            if text:
                return text
            return "### Grid cell %d\n\n(no description)" % (index + 1,)
        cell_id = _coerce_str(data.get("id"), "cell-%d" % (index + 1,)).strip()
        description = _coerce_str(
            data.get("description", data.get("choice", ""))).strip()
        if not cell_id:
            cell_id = "cell-%d" % (index + 1,)
        if not description:
            description = "(no description)"
        lines = ["### Grid cell `%s`" % cell_id, "", description]
        for key in ("controls", "se_choice", "sample_window"):
            if key in data:
                lines.append("- %s: %s" % (key, _coerce_str(data.get(key))))
        return "\n".join(lines)
    except Exception:
        return "### Grid cell %d\n\n(no description)" % (index + 1,)


def _coerce_grid_cells(grid_cells: Any) -> list:
    """Coerce grid input to a list of entries; never raises."""
    try:
        if grid_cells is None:
            return []
        if isinstance(grid_cells, (list, tuple)):
            return list(grid_cells)
        return [grid_cells]
    except Exception:
        return []


def _fallback_cell(cell_type: str, source: str) -> dict:
    """Hand-built cell dict with a unique id (no nbformat needed)."""
    cell: dict = {
        "id": _new_id(),
        "cell_type": cell_type,
        "metadata": {},
        "source": source,
    }
    if cell_type == "code":
        cell["execution_count"] = None
        cell["outputs"] = []
    return cell


def _ensure_ids(cells: list) -> None:
    """Fill in missing/duplicate cell ids in place; never raises."""
    try:
        seen: set = set()
        for cell in cells:
            try:
                cid = cell.get("id") if isinstance(cell, dict) else None
            except Exception:
                cid = None
            if not cid or not isinstance(cid, str) or cid in seen:
                cid = _new_id()
                while cid in seen:
                    cid = _new_id()
                try:
                    cell["id"] = cid
                except Exception:
                    continue
            seen.add(cid)
    except Exception:
        pass


def build_notebook(
    code: Any = "",
    grid_cells: Any = None,
    paper_id: Any = "",
    claim: Any = "",
) -> dict:
    """Build an unexecuted nbformat-v4 notebook dict; never raises.

    Cell 0 is a markdown receipt header (``paper_id``, claim), cell 1 is
    the analysis code cell, then one markdown cell per grid entry
    (capped at :data:`MAX_GRID_CELLS`). Uses ``nbformat.v4`` helpers
    when importable, else hand-built dicts with unique ``id`` fields.
    """
    try:
        source = _coerce_str(code, "")
    except Exception:
        source = ""
    try:
        pid = _coerce_str(paper_id, "").strip() or "unknown"
    except Exception:
        pid = "unknown"
    try:
        claim_text = _coerce_str(claim, "").strip() or "none"
    except Exception:
        claim_text = "none"
    header = (
        "# Receipt \u2014 executed analysis notebook\n\n"
        "paper: %s\n\nclaim: %s\n\n"
        "Every number on the verdict card traces to an executed cell output below.\n"
        % (pid, claim_text)
    )
    entries = _coerce_grid_cells(grid_cells)[:MAX_GRID_CELLS]
    grid_sources = [_grid_cell_text(entry, i) for i, entry in enumerate(entries)]
    if not source.strip():
        source = "# no analysis code provided\n"
    metadata = {"paper_id": pid, "claim": claim_text}
    try:
        from nbformat.v4 import (  # noqa: PLC0415 - optional dep, lazy probe
            new_code_cell,
            new_markdown_cell,
            new_notebook,
        )

        cells = [new_markdown_cell(header), new_code_cell(source)]
        for text in grid_sources:
            cells.append(new_markdown_cell(text))
        notebook = new_notebook(cells=cells, metadata=dict(metadata))
        try:
            notebook["nbformat"] = 4
            notebook["nbformat_minor"] = 5
        except Exception:
            pass
        try:
            _ensure_ids(notebook["cells"])
        except Exception:
            pass
        try:
            import json as _json

            return _json.loads(_json.dumps(notebook))
        except Exception:
            return dict(notebook)
    except Exception:
        cells = [
            _fallback_cell("markdown", header),
            _fallback_cell("code", source),
        ]
        for text in grid_sources:
            cells.append(_fallback_cell("markdown", text))
        return {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": dict(metadata),
            "cells": cells,
        }


def _coerce_timeout(value: Any) -> float:
    """Clamp ``value`` into ``(0, 300]`` seconds; default 60s."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT_S
    try:
        if isinstance(number, float) and math.isnan(number):
            return DEFAULT_TIMEOUT_S
        if not math.isfinite(number) or number <= 0:
            return DEFAULT_TIMEOUT_S
    except Exception:
        return DEFAULT_TIMEOUT_S
    return min(number, MAX_TIMEOUT_S)


def _cell_source(cell: Any) -> str:
    """Extract executable source from a code cell; never raises."""
    try:
        if not isinstance(cell, dict):
            return ""
        source = cell.get("source", "")
        if isinstance(source, list):
            return "".join(_coerce_str(part) for part in source)
        return _coerce_str(source)
    except Exception:
        return ""


def _stream_output(name: str, text: str) -> dict:
    return {"output_type": "stream", "name": name, "text": text}


def _error_output(ename: str, evalue: str, traceback_lines: list) -> dict:
    return {
        "output_type": "error",
        "ename": ename,
        "evalue": evalue,
        "traceback": list(traceback_lines),
    }


def _run_source(source: str, timeout_s: float) -> tuple:
    """Run one cell source in an isolated subprocess; never raises.

    Returns ``(outputs, execution_ok)`` where ``outputs`` is a list of
    nbformat output dicts.
    """
    outputs: list = []
    try:
        proc = subprocess.run(
            [sys.executable, "-c", source],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout or ""
        err = exc.stderr or ""
        if isinstance(out, bytes):
            out = out.decode("utf-8", "replace")
        if isinstance(err, bytes):
            err = err.decode("utf-8", "replace")
        stdout = _coerce_str(out)
        stderr = _coerce_str(err)
        if stdout:
            outputs.append(_stream_output("stdout", stdout))
        if stderr:
            outputs.append(_stream_output("stderr", stderr))
        note = "hard kill at %.1fs timebox" % timeout_s
        outputs.append(_error_output("TimeoutError", note, [note]))
        return outputs, False
    except Exception as exc:
        note = "%s: %s" % (type(exc).__name__, exc)
        outputs.append(_error_output(type(exc).__name__, str(exc), [note]))
        return outputs, False
    stdout = proc.stdout if isinstance(proc.stdout, str) else _coerce_str(
        proc.stdout)
    stderr = proc.stderr if isinstance(proc.stderr, str) else _coerce_str(
        proc.stderr)
    if stdout:
        outputs.append(_stream_output("stdout", stdout))
    if stderr:
        outputs.append(_stream_output("stderr", stderr))
    exit_code = int(getattr(proc, "returncode", 0) or 0)
    if exit_code != 0:
        last_line = ""
        try:
            for line in stderr.splitlines():
                if line.strip():
                    last_line = line.strip()
            if not last_line:
                for line in stdout.splitlines():
                    if line.strip():
                        last_line = line.strip()
        except Exception:
            last_line = ""
        evalue = last_line or ("exit code %d" % exit_code)
        traceback_lines = [stderr] if stderr else [evalue]
        outputs.append(_error_output("CalledProcessError", evalue,
                                     traceback_lines))
        return outputs, False
    return outputs, True


def _execute_fake(nb: dict, timeout_s: float) -> dict:
    """Execute each code cell via a subprocess; never raises."""
    counter = 0
    try:
        cells = nb.get("cells")
    except Exception:
        cells = None
    if not isinstance(cells, list):
        try:
            nb["cells"] = []
        except Exception:
            return nb
        return nb
    for cell in cells:
        try:
            if not isinstance(cell, dict):
                continue
            if cell.get("cell_type") != "code":
                continue
            source = _cell_source(cell)
            if not source.strip():
                cell["outputs"] = []
                try:
                    cell["execution_count"] = None
                except Exception:
                    pass
                continue
            counter += 1
            outputs, _ok = _run_source(source, timeout_s)
            cell["outputs"] = outputs
            try:
                cell["execution_count"] = counter
            except Exception:
                pass
        except Exception as exc:  # honest failure goes into outputs
            try:
                note = "%s: %s" % (type(exc).__name__, exc)
                cell["outputs"] = [_error_output(
                    type(exc).__name__, str(exc), [note])]
            except Exception:
                pass
    return nb


def _execute_with_nbclient(nb: dict, timeout_s: float) -> dict:
    """Execute via ``nbclient``; raises on any failure (caller falls back)."""
    import nbformat  # noqa: PLC0415 - optional dep, online path only
    from nbclient import NotebookClient  # noqa: PLC0415 - online path only

    node = nbformat.from_dict(nb)
    client = NotebookClient(node, timeout=timeout_s, kernel_name="python3")
    client.execute()
    import json as _json

    return _json.loads(nbformat.writes(node))


def _invalid_notebook(value: Any) -> dict:
    """Honest artifact for ragged input: a valid-shape notebook with error."""
    note = "invalid notebook input: expected a notebook dict, got %s" % (
        type(value).__name__)
    cell = _fallback_cell("code", "# no analysis code provided\n")
    cell["outputs"] = [_error_output("ValueError", note, [note])]
    cell["execution_count"] = None
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {},
        "cells": [cell],
    }


def execute_notebook(nb: Any, timeout: Any = DEFAULT_TIMEOUT_S) -> dict:
    """Execute a notebook dict and return it with cell outputs; never raises.

    Offline (``QED_OFFLINE`` unset/empty/truthy, the default) runs the
    fake executor: one ``sys.executable -c`` subprocess per code cell.
    Online tries ``nbclient`` with the default ``python3`` kernel and
    falls back to the fake executor on any error. Ragged input is
    returned as a valid-shape notebook carrying an error output.
    """
    try:
        nb_copy = copy.deepcopy(nb)
    except Exception:
        nb_copy = None
    if not isinstance(nb_copy, dict):
        return _invalid_notebook(nb)
    try:
        if not isinstance(nb_copy.get("cells"), list):
            nb_copy["cells"] = []
    except Exception:
        return _invalid_notebook(nb)
    try:
        if nb_copy.get("nbformat") != 4:
            nb_copy["nbformat"] = 4
        if nb_copy.get("nbformat_minor") != 5:
            nb_copy["nbformat_minor"] = 5
        if not isinstance(nb_copy.get("metadata"), dict):
            nb_copy["metadata"] = {}
    except Exception:
        pass
    timeout_s = _coerce_timeout(timeout)
    try:
        offline = parse_offline(os.environ.get("QED_OFFLINE"))
    except Exception:
        offline = True
    if not offline:
        try:
            return _execute_with_nbclient(nb_copy, timeout_s)
        except Exception:
            pass
    try:
        return _execute_fake(nb_copy, timeout_s)
    except Exception:
        return _invalid_notebook(nb)


def build_and_execute(
    code: Any = "",
    grid_cells: Any = None,
    paper_id: Any = "",
    claim: Any = "",
    timeout: Any = DEFAULT_TIMEOUT_S,
) -> dict:
    """Build then execute a receipt notebook; never raises on input shape."""
    try:
        notebook = build_notebook(code, grid_cells, paper_id, claim)
    except Exception:
        notebook = _invalid_notebook(code)
    try:
        return execute_notebook(notebook, timeout)
    except Exception:
        return notebook if isinstance(notebook, dict) else _invalid_notebook(
            code)


def _output_texts(output: Any) -> list:
    """Collect searchable strings from one output; never raises."""
    texts: list = []
    try:
        if output is None:
            return texts
        if isinstance(output, str):
            texts.append(output)
            return texts
        if not isinstance(output, dict):
            texts.append(_coerce_str(output))
            return texts
        for key in ("text", "evalue"):
            try:
                value = output.get(key)
            except Exception:
                continue
            if isinstance(value, str) and value:
                texts.append(value)
            elif isinstance(value, list) and value:
                texts.append("".join(_coerce_str(p) for p in value))
        try:
            traceback_value = output.get("traceback")
        except Exception:
            traceback_value = None
        if isinstance(traceback_value, list):
            texts.append(
                "\n".join(_coerce_str(p) for p in traceback_value))
        elif isinstance(traceback_value, str) and traceback_value:
            texts.append(traceback_value)
        try:
            data = output.get("data")
        except Exception:
            data = None
        if isinstance(data, dict):
            for value in data.values():
                if isinstance(value, str) and value:
                    texts.append(value)
                elif isinstance(value, list) and value:
                    texts.append("".join(_coerce_str(p) for p in value))
    except Exception:
        pass
    return texts


def extract_numbers(nb: Any) -> list:
    """Scan code-cell outputs for floats; deduped first-seen order.

    Never raises; ragged input yields ``[]``.
    """
    found: list = []
    seen: set = set()
    try:
        cells = nb.get("cells", []) if isinstance(nb, dict) else []
    except Exception:
        return []
    try:
        if not isinstance(cells, list):
            return []
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
                for text in _output_texts(output):
                    try:
                        matches = _NUMBER_RE.findall(text)
                    except Exception:
                        continue
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
                        if value not in seen:
                            seen.add(value)
                            found.append(value)
    except Exception:
        pass
    return found
