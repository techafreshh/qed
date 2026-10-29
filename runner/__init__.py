"""Sandbox runner package (issue #14) with offline cached-run replay (issue #15)
and receipt notebook builder (issue #18)."""

from runner.offline import NotFound, replay
from runner.sandbox import RunResult, run_code

__all__ = [
    "NotFound",
    "RunResult",
    "build_and_execute",
    "build_notebook",
    "execute_notebook",
    "extract_numbers",
    "replay",
    "run_code",
]


def __getattr__(name):
    # Lazy so ``import runner`` never requires the optional nbformat dep.
    if name in ("build_and_execute", "build_notebook", "execute_notebook",
                "extract_numbers"):
        from runner import notebook as _notebook

        return getattr(_notebook, name)
    raise AttributeError("module %r has no attribute %r" % (__name__, name))
