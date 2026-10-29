"""Codegen backend port package."""

from codegen.base import (
    CodegenBackend,
    LlamaDirectBackend,
    RecursionGuardError,
    check_recursion_guard,
)

try:
    from codegen.muse_backend import CodegenUnavailable, MuseBackend
except ImportError:
    from codegen.base import MuseBackend

    class CodegenUnavailable(RuntimeError):
        """Raised when a codegen backend cannot produce code."""

try:
    from codegen.pi_backend import PiBackend
except ImportError:
    from codegen.base import PiBackend

try:
    from codegen.llama_backend import LlamaBackend
except ImportError:
    LlamaBackend = LlamaDirectBackend

try:
    from codegen.factory import BACKENDS, DEFAULT_BACKEND, get_backend
except ImportError:
    BACKENDS = {}
    DEFAULT_BACKEND = "llama_direct"

    def get_backend(name=None):  # pragma: no cover - factory is always present
        raise CodegenUnavailable("codegen factory unavailable")

__all__ = [
    "RecursionGuardError",
    "check_recursion_guard",
    "CodegenBackend",
    "CodegenUnavailable",
    "MuseBackend",
    "PiBackend",
    "LlamaDirectBackend",
    "LlamaBackend",
    "BACKENDS",
    "DEFAULT_BACKEND",
    "get_backend",
]
