"""Honest-refusal predicates for adversarial inputs (issue #27).

Centralizes the checks the API, the orchestrator, and the probes share:
a vague-claim predicate, a banned-import static scanner, and a
missing-file predicate. Stdlib only: ``ast`` for the import scan, no
network, no subprocess, no file writes. Mirrors the ``ExtractionFailed``
honest-failure style in ``agent/extract.py``.
"""

from __future__ import annotations

import ast

# Normalized (lowercased, punctuation-stripped) claims too underspecified
# to falsify. Membership only: short-but-real claims such as "test" or
# "wages rise" must NOT match, so the API's existing 202 paths keep working.
VAGUE_CLAIMS = frozenset(
    {
        "it works",
        "it works well",
        "works",
        "it is true",
        "its true",
        "it replicates",
        "replicates",
        "true",
        "significant",
        "it is significant",
        "the effect is real",
        "the effect exists",
        "the claim holds",
        "the result holds",
        "result holds",
        "it holds",
    }
)

# Proprietary toolchains unavailable in the locked offline sandbox.
BANNED_IMPORTS = frozenset({"stata", "sas", "matlab", "spss", "eviews"})


class Refused(Exception):
    """Honest refusal: the run cannot proceed, with a human-readable reason."""

    def __init__(self, reason: str):
        self.reason = reason if isinstance(reason, str) and reason.strip() else "refused"
        super().__init__(self.reason)


def _normalize_claim(claim) -> str:
    """Lowercase, strip surrounding punctuation/space, collapse whitespace."""
    if not isinstance(claim, str):
        return ""
    text = claim.strip().lower()
    while text and text[-1] in ".!?,":
        text = text[:-1].rstrip()
    while text and text[0] in ".!?,":
        text = text[1:].lstrip()
    return " ".join(text.split())


def is_vague_claim(claim) -> bool:
    """True when ``claim`` is too underspecified to falsify."""
    if not isinstance(claim, str) or not claim.strip():
        return False
    return _normalize_claim(claim) in VAGUE_CLAIMS


def _banned_top_level(name: str) -> str | None:
    """Return the banned top-level module in ``name``, else None."""
    if not isinstance(name, str) or not name.strip():
        return None
    top = name.split(".")[0].strip().lower()
    return top if top in BANNED_IMPORTS else None


def check_banned_imports(code: str) -> None:
    """Raise :class:`Refused` naming the first banned import in ``code``.

    Static ``ast`` scan only; never executes code. Unparseable snippets
    are ignored here (``compile`` elsewhere reports them).
    """
    if not isinstance(code, str) or not code.strip():
        return
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError, MemoryError, RecursionError):
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                hit = _banned_top_level(getattr(alias, "name", ""))
                if hit is not None:
                    raise Refused(
                        "banned import %r is not available in the offline "
                        "sandbox; refusing to run" % hit
                    )
        elif isinstance(node, ast.ImportFrom):
            hit = _banned_top_level(getattr(node, "module", "") or "")
            if hit is not None:
                raise Refused(
                    "banned import %r is not available in the offline "
                    "sandbox; refusing to run" % hit
                )


def check_missing_file(paper_id: str, exists: bool) -> None:
    """Raise :class:`Refused` when the required input file is absent."""
    if exists:
        return
    raise Refused(
        "missing input file for paper %r; refusing to invent a result" % (paper_id,)
    )
