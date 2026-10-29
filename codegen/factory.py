"""Backend selection factory for the codegen port (issue #13).

Maps the ``muse`` / ``pi`` / ``llama_direct`` backend names to fresh
backend instances. Stdlib only.
"""

from __future__ import annotations

import os

from codegen.llama_backend import LlamaBackend
from codegen.muse_backend import CodegenUnavailable, MuseBackend
from codegen.pi_backend import PiBackend

__all__ = ["BACKENDS", "DEFAULT_BACKEND", "get_backend"]

BACKENDS = {
    "muse": MuseBackend,
    "pi": PiBackend,
    "llama_direct": LlamaBackend,
}

DEFAULT_BACKEND = "llama_direct"


def get_backend(name=None):
    """Return a fresh backend instance for ``name``.

    ``None`` or a blank name falls back to ``QED_CODEGEN_BACKEND`` and
    then to ``llama_direct``. Names are case- and whitespace-tolerant.
    Unknown names raise ``CodegenUnavailable``.
    """
    if name is not None and callable(getattr(name, "author", None)):
        return name
    if name is None or (isinstance(name, str) and name.strip() == ""):
        name = os.environ.get("QED_CODEGEN_BACKEND", DEFAULT_BACKEND)
    key = str(name).strip().lower() if isinstance(name, str) else ""
    if key in BACKENDS:
        return BACKENDS[key]()
    if key in ("llama-direct", "llama"):
        return LlamaBackend()
    raise CodegenUnavailable("unknown codegen backend: %r" % (name,))
