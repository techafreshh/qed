"""Modal sandbox runner with frozen images (PRD sections 5 and 9).

Analysis code executes only inside a locked, time-boxed Modal sandbox;
never on the host. Stdlib only at import time. The live path lazily
imports ``modal`` and is never hit when ``QED_OFFLINE=1``.
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from typing import Any

from app.config import parse_offline

logger = logging.getLogger("runner.sandbox")

ALLOWED_IMAGES = ("stats", "ml")
MAX_TIMEBOX_S = 300.0
TIMEOUT_EXIT_CODE = 124

_IMAGES_DIR = os.path.join(os.path.dirname(__file__), "images")
# Live-path egress: pip index only, nothing else.
PIP_EGRESS_ALLOWLIST = ["pypi.org", "files.pythonhosted.org"]


@dataclass
class RunResult:
    """Result of one sandboxed code execution."""

    stdout: str = ""
    stderr: str = ""
    notebook: dict = field(default_factory=dict)
    cell_outputs: list = field(default_factory=list)
    exit_code: int = 0
    duration_s: float = 0.0

    @property
    def exit(self) -> int:  # alias for the ``exit`` spelling in issue #14
        return self.exit_code

    def __getitem__(self, key: str) -> Any:
        aliases = {
            "exit": "exit_code",
            "exit_code": "exit_code",
            "stdout": "stdout",
            "stderr": "stderr",
            "notebook": "notebook",
            "cell_outputs": "cell_outputs",
            "cell-outputs": "cell_outputs",
            "duration_s": "duration_s",
            "duration": "duration_s",
        }
        attr = aliases.get(key, key)
        if attr in ("stdout", "stderr", "notebook", "cell_outputs",
                    "exit_code", "duration_s"):
            return getattr(self, attr)
        raise KeyError(key)


def _clamp_timebox(timebox: Any) -> float:
    """Clamp ``timebox`` into ``(0, 300]`` seconds (hard kill at 300s)."""
    try:
        value = float(timebox)
    except (TypeError, ValueError):
        return MAX_TIMEBOX_S
    if isinstance(value, float) and math.isnan(value):
        return MAX_TIMEBOX_S
    if not math.isfinite(value) or value <= 0:
        return 1.0 if value <= 0 else MAX_TIMEBOX_S
    return min(value, MAX_TIMEBOX_S)


def _image_digest(image: str) -> str:
    """Resolve the audit digest for ``image``.

    Returns the sha256 of the frozen Dockerfile when no built digest is
    available, else ``"unknown"``.
    """
    path = os.path.join(_IMAGES_DIR, "%s.Dockerfile" % image)
    try:
        with open(path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()
    except OSError:
        return "unknown"


def _build_notebook(code: str, stdout: str, stderr: str,
                     exit_code: int) -> dict:
    """Build a minimal nbformat-4 dict by hand (no third-party imports)."""
    outputs: list = []
    if stdout:
        outputs.append({
            "output_type": "stream",
            "name": "stdout",
            "text": stdout,
        })
    if stderr:
        outputs.append({
            "output_type": "stream",
            "name": "stderr",
            "text": stderr,
        })
    if not outputs:
        outputs.append({
            "output_type": "stream",
            "name": "stdout",
            "text": "",
        })
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {},
        "cells": [
            {
                "cell_type": "code",
                "execution_count": 1,
                "metadata": {},
                "source": code,
                "outputs": outputs,
            }
        ],
    }


def _write_data_files(tmpdir: str, data: Any) -> None:
    """Mount ``data`` (filename -> bytes) as input files under ``tmpdir``."""
    if not data:
        return
    items = data.items() if isinstance(data, dict) else []
    for name, content in items:
        filename = str(name)
        if not filename or filename.strip() == "":
            raise ValueError("data filename must be non-empty")
        # Reject absolute paths and parent traversal.
        normalized = os.path.normpath(filename)
        if os.path.isabs(normalized) or normalized.startswith(".."):
            raise ValueError("unsafe data filename: %r" % (filename,))
        target = os.path.join(tmpdir, normalized)
        if not os.path.realpath(target).startswith(os.path.realpath(tmpdir)):
            raise ValueError("unsafe data filename: %r" % (filename,))
        parent = os.path.dirname(target)
        if parent:
            os.makedirs(parent, exist_ok=True)
        blob = content if isinstance(content, bytes) else str(content).encode()
        with open(target, "wb") as handle:
            handle.write(blob)


def _run_fake(code: str, data: Any, timebox: float) -> RunResult:
    """Execute ``code`` in an isolated subprocess (offline/test path)."""
    started = time.monotonic()
    stdout = ""
    stderr = ""
    exit_code = 0
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_data_files(tmpdir, data)
            # Persist the snippet for audit; execution still goes through
            # ``sys.executable -c`` so user code never runs in-process.
            try:
                with open(os.path.join(tmpdir, "main.py"), "w",
                           encoding="utf-8") as handle:
                    handle.write(code)
            except OSError:
                pass
            try:
                proc = subprocess.run(
                    [sys.executable, "-c", code],
                    cwd=tmpdir,
                    capture_output=True,
                    text=True,
                    timeout=timebox,
                )
                stdout = proc.stdout if proc.stdout is not None else ""
                stderr = proc.stderr if proc.stderr is not None else ""
                exit_code = int(proc.returncode)
            except subprocess.TimeoutExpired as exc:
                out = exc.stdout or ""
                err = exc.stderr or ""
                if isinstance(out, bytes):
                    out = out.decode("utf-8", "replace")
                if isinstance(err, bytes):
                    err = err.decode("utf-8", "replace")
                stdout = str(out)
                note = ("hard kill at %.1fs timebox" % timebox)
                stderr = (str(err) + ("\n" if err else "") + note)
                exit_code = TIMEOUT_EXIT_CODE
    except Exception as exc:  # never raise on bad user code
        stdout = ""
        stderr = "%s: %s" % (type(exc).__name__, exc)
        exit_code = 1
    duration_s = time.monotonic() - started
    if duration_s < 0:
        duration_s = 0.0
    notebook = _build_notebook(code, stdout, stderr, exit_code)
    cell_outputs: list = []
    if stdout:
        cell_outputs.append(stdout)
    if stderr and exit_code != 0:
        cell_outputs.append(stderr)
    if not cell_outputs and stdout == "" and stderr == "":
        cell_outputs = []
    return RunResult(
        stdout=stdout,
        stderr=stderr,
        notebook=notebook,
        cell_outputs=cell_outputs,
        exit_code=exit_code,
        duration_s=duration_s,
    )


def _data_blobs(data: Any):
    """Validate ``data`` filenames and yield ``(name, bytes)`` pairs."""
    if not data:
        return
    items = data.items() if isinstance(data, dict) else []
    for name, content in items:
        filename = str(name)
        if not filename or filename.strip() == "":
            raise ValueError("data filename must be non-empty")
        normalized = os.path.normpath(filename)
        if os.path.isabs(normalized) or normalized.startswith(".."):
            raise ValueError("unsafe data filename: %r" % (filename,))
        blob = content if isinstance(content, bytes) else str(
            content).encode()
        yield normalized, blob


def _run_live(code: str, image: str, data: Any, timebox: float) -> RunResult:
    """Execute ``code`` in a locked Modal sandbox (live path only)."""
    try:
        import modal
    except ImportError as exc:
        raise RuntimeError(
            "modal package is required for live sandbox runs: "
            "pip install 'modal>=1.0'"
        ) from exc
    started = time.monotonic()
    # Both bounds are seconds: sandbox lifetime and exec deadline.
    timeout_s = max(1, int(math.ceil(timebox)))
    dockerfile = os.path.join(_IMAGES_DIR, "%s.Dockerfile" % image)
    modal_image = modal.Image.from_dockerfile(dockerfile)
    # Fail closed: no fallback may drop the egress restriction.
    sandbox = modal.Sandbox.create(
        image=modal_image,
        timeout=timeout_s,
        outbound_domain_allowlist=PIP_EGRESS_ALLOWLIST,
    )
    try:
        for filename, blob in _data_blobs(data):
            sandbox.filesystem.write_bytes(blob, "/tmp/" + filename)
        proc = sandbox.exec("python3", "-c", code, timeout=timeout_s)
        exit_code = int(proc.wait())
        stdout = proc.stdout.read() or ""
        stderr = proc.stderr.read() or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", "replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", "replace")
        if exit_code == -1:
            # Exec deadline exceeded: the sandbox killed the run.
            note = "hard kill at %.1fs timebox" % timebox
            stderr = (stderr + ("\n" if stderr else "") + note)
            duration_s = time.monotonic() - started
            notebook = _build_notebook(code, stdout, stderr,
                                       TIMEOUT_EXIT_CODE)
            cell_outputs = []
            if stdout:
                cell_outputs.append(stdout)
            cell_outputs.append(note)
            return RunResult(
                stdout=stdout,
                stderr=stderr,
                notebook=notebook,
                cell_outputs=cell_outputs,
                exit_code=TIMEOUT_EXIT_CODE,
                duration_s=max(duration_s, 0.0),
            )
        duration_s = time.monotonic() - started
        if duration_s < 0:
            duration_s = 0.0
        notebook = _build_notebook(code, stdout, stderr, exit_code)
        cell_outputs = []
        if stdout:
            cell_outputs.append(stdout)
        if stderr and exit_code != 0:
            cell_outputs.append(stderr)
        return RunResult(
            stdout=stdout,
            stderr=stderr,
            notebook=notebook,
            cell_outputs=cell_outputs,
            exit_code=exit_code,
            duration_s=duration_s,
        )
    finally:
        try:
            sandbox.terminate()
        except Exception:
            pass


def run_code(code: str, image: str = "stats", data: Any = None,
             timebox: Any = 300) -> RunResult:
    """Run ``code`` in a locked sandbox and return a :class:`RunResult`.

    ``image`` is ``"stats"`` or ``"ml"`` (else ``ValueError``).
    ``data`` is an optional ``dict[str, bytes]`` of filename -> content
    mounted as input files. ``timebox`` is clamped into ``(0, 300]``.
    Offline (``QED_OFFLINE=1`` or no ``MODAL_TOKEN``) uses the in-repo
    fake sandbox; otherwise the live Modal path runs with a hard kill at
    300s. Audit fields (sha256, image digest, duration) are logged.
    """
    if image not in ALLOWED_IMAGES:
        raise ValueError("unknown image %r (expected one of %r)" % (
            image, ALLOWED_IMAGES))
    if not isinstance(code, str):
        code = str(code)
    clamped = _clamp_timebox(timebox)
    code_sha256 = hashlib.sha256(code.encode("utf-8")).hexdigest()
    digest = _image_digest(image)
    offline = parse_offline(os.environ.get("QED_OFFLINE")) or not (
        os.environ.get("MODAL_TOKEN") or "").strip()
    if offline:
        result = _run_fake(code, data, clamped)
    else:
        result = _run_live(code, image, data, clamped)
    logger.info(
        "sandbox run sha256=%s image=%s digest=%s duration_s=%.3f "
        "exit_code=%s",
        code_sha256, image, digest, result.duration_s, result.exit_code,
    )
    return result
