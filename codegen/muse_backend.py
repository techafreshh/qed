"""Muse code author via pi running the Muse Spark model (issue #13).

Offline-first: return a deterministic honest template when
``QED_OFFLINE`` opts into offline mode or the ``pi`` binary is missing.
Attempt exactly one ``pi --model <model> -p`` subprocess call otherwise,
with a hard timeout. Any subprocess failure maps to
``CodegenUnavailable``. Stdlib only: no network, no new dependencies.
"""

from __future__ import annotations

import os
import shutil
import subprocess

from app.config import parse_offline
from codegen.base import (
    CodegenBackend,
    RecursionGuardError,
    check_recursion_guard,
)

try:
    from codegen.pi_backend import CodegenUnavailable
except ImportError:  # pragma: no cover - pi_backend is always present

    class CodegenUnavailable(RuntimeError):
        """Raised when the muse backend cannot produce code."""


__all__ = ["CodegenUnavailable", "MUSE_MODEL", "PROMPT_TEMPLATE", "MuseBackend"]

_SUBPROCESS_TIMEOUT = 60

MUSE_MODEL = "muse-spark-1.3-contributor"

PROMPT_TEMPLATE = (
    "Write a replication analysis Python script.\n"
    "Return Python code only, no prose.\n"
    "The script must define def analyze(spec=None, dataset_profile=None).\n"
    "Spec: {spec}\n"
    "Dataset profile: {profile}\n"
    "Prior traceback (if any): {traceback}\n"
)


def _label(value) -> str:
    """Coerce ragged spec/profile/traceback input to a short label.

    Never raises: ``None`` maps to ``""``, everything else goes through
    ``repr()`` collapsed to one line and truncated.
    """
    try:
        if value is None:
            return ""
        if isinstance(value, dict):
            parts = []
            for key in ("id", "claim", "estimator"):
                item = value.get(key)
                if item is not None and str(item).strip() != "":
                    parts.append("%s=%s" % (key, str(item).strip()))
            if parts:
                return " ".join(parts)[:500]
            return _label(repr(value))
        collapsed = " ".join(repr(value).split())
        return collapsed[:2000]
    except Exception:
        return ""


def _offline_template(spec=None, dataset_profile=None, prior_traceback=None) -> str:
    """Build the honest offline template (no subprocess, no network)."""
    header = [
        "# backend=muse offline template (no subprocess, no network)",
        "# spec: %s" % _label(spec),
        "# dataset_profile: %s" % _label(dataset_profile),
    ]
    return (
        "\n".join(header)
        + "\n"
        + '"""Offline muse codegen output; pi binary missing or QED_OFFLINE=1."""\n'
        + "\n\n"
        + "def analyze(spec=None, dataset_profile=None):\n"
        + '    """Offline replication analysis entrypoint."""\n'
        + '    return {"ok": True, "backend": "muse"}\n'
    )


class MuseBackend(CodegenBackend):
    """Muse code author via ``pi --model <muse-spark> -p`` subprocess."""

    def author(self, spec, dataset_profile=None, prior_traceback=None) -> str:
        """Author Python source for ``spec`` against ``dataset_profile``."""
        check_recursion_guard()
        if parse_offline(os.environ.get("QED_OFFLINE")):
            return _offline_template(spec, dataset_profile, prior_traceback)
        if shutil.which("pi") is None:
            return _offline_template(spec, dataset_profile, prior_traceback)
        model = os.environ.get("QED_MUSE_MODEL", "").strip() or MUSE_MODEL
        rendered = PROMPT_TEMPLATE.format(
            spec=_label(spec),
            profile=_label(dataset_profile),
            traceback=_label(prior_traceback),
        )
        try:
            result = subprocess.run(
                ["pi", "--model", model, "-p", rendered],
                capture_output=True,
                text=True,
                timeout=_SUBPROCESS_TIMEOUT,
            )
        except FileNotFoundError as exc:
            raise CodegenUnavailable("pi binary not found") from exc
        except subprocess.TimeoutExpired as exc:
            raise CodegenUnavailable("pi subprocess timed out") from exc
        except OSError as exc:
            raise CodegenUnavailable("pi subprocess failed: %s" % exc) from exc
        if result.returncode != 0:
            raise CodegenUnavailable(
                "pi exited with status %s" % result.returncode
            )
        code = (result.stdout or "").strip()
        if not code:
            raise CodegenUnavailable("pi returned empty output")
        return code
