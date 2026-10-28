"""Codegen port with recursion guard (PRD sections 6 and 9).

Stdlib only, offline stubs: no subprocess, no network, no credentials.
"""

import abc
import os

_GUARD_VARS = ("OPENCODE_INVOKED_BY", "QED_AGENT_DEPTH")


class RecursionGuardError(RuntimeError):
    """Raised when codegen runs inside an agent invocation."""


def check_recursion_guard() -> None:
    """Refuse recursive agent invocation before any other work.

    Raises RecursionGuardError naming the offending variable when
    ``OPENCODE_INVOKED_BY`` or ``QED_AGENT_DEPTH`` is present in
    ``os.environ`` with a non-empty-after-strip value. Returns ``None``
    otherwise.
    """
    for var in _GUARD_VARS:
        value = os.environ.get(var)
        if value is not None and value.strip() != "":
            raise RecursionGuardError(
                "recursive agent invocation refused: %s is set" % var
            )


def _offline_stub(backend: str) -> str:
    return (
        "# backend=%s offline stub\n"
        '"""Offline stub codegen output; no subprocess, no network."""\n'
        "\n\n"
        "def analyze(spec=None, dataset_profile=None):\n"
        '    """Offline placeholder analysis entrypoint."""\n'
        "    return {%r: True}\n" % (backend, backend)
    )


class CodegenBackend(abc.ABC):
    """Shared port for code author backends.

    Every concrete ``author`` override must call
    ``check_recursion_guard()`` first.
    """

    @abc.abstractmethod
    def author(self, spec, dataset_profile, prior_traceback=None) -> str:
        """Author Python source for ``spec`` against ``dataset_profile``."""
        raise NotImplementedError


class MuseBackend(CodegenBackend):
    """Muse code author backend (offline stub)."""

    def author(self, spec, dataset_profile, prior_traceback=None) -> str:
        check_recursion_guard()
        return _offline_stub("muse")


class PiBackend(CodegenBackend):
    """Pi code author backend (offline stub)."""

    def author(self, spec, dataset_profile, prior_traceback=None) -> str:
        check_recursion_guard()
        return _offline_stub("pi")


class LlamaDirectBackend(CodegenBackend):
    """Llama direct code author backend (offline stub)."""

    def author(self, spec, dataset_profile, prior_traceback=None) -> str:
        check_recursion_guard()
        return _offline_stub("llama_direct")
