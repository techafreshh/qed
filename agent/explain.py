"""Llama verdict narration (issue #17): narrates, never decides.

Pure narration layer over an already-decided verdict: never imports
``rubric``, never recomputes or overrides the verdict, never does I/O
itself beyond a single delegated ``agent.llm.complete`` call.
"""

import os

from app.config import parse_offline

EXPLAIN_MAX_TOKENS = 128
_MAX_GRID_CHARS = 800


def _offline_text(verdict, fragile_choice) -> str:
    verdict_text = "unknown" if verdict is None or not str(verdict).strip() else str(verdict)
    fragile_text = (
        "unknown" if fragile_choice is None or not str(fragile_choice).strip() else str(fragile_choice)
    )
    return (
        f"Verdict: {verdict_text}. "
        f"Fragile choice: {fragile_text}. "
        "This narration describes the decided verdict card; it does not decide."
    )


def _build_prompt(verdict, grid_results, fragile_choice) -> str:
    try:
        grid_text = repr(grid_results)
    except Exception:
        grid_text = "unavailable"
    if len(grid_text) > _MAX_GRID_CHARS:
        grid_text = grid_text[:_MAX_GRID_CHARS] + "..."
    return (
        "Narrate the given verdict for a verdict card; "
        "do NOT decide, recompute, or change it. "
        "Name the fragile analytical choice verbatim in one short paragraph.\n"
        f"Verdict: {verdict}\n"
        f"Fragile choice: {fragile_choice}\n"
        f"Grid summary: {grid_text}\n"
        "Narration:"
    )


def _resolve_complete(complete_fn):
    if complete_fn is not None:
        return complete_fn
    try:
        from agent.llm import complete as llm_complete
    except ImportError:
        return None
    return llm_complete


def explain(verdict, grid_results=None, fragile_choice="", complete_fn=None) -> str:
    """Narrate an already-decided verdict; never decides or calls the rubric."""
    if parse_offline(os.environ.get("QED_OFFLINE")):
        return _offline_text(verdict, fragile_choice)
    complete = _resolve_complete(complete_fn)
    if complete is None:
        return _offline_text(verdict, fragile_choice)
    try:
        prompt = _build_prompt(verdict, grid_results, fragile_choice)
        result = complete(prompt, EXPLAIN_MAX_TOKENS)
    except Exception:
        return _offline_text(verdict, fragile_choice)
    if not isinstance(result, str) or not result.strip():
        return _offline_text(verdict, fragile_choice)
    return result.strip()
