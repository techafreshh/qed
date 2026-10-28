"""Claim extraction: prose to falsifiable spec JSON (issue #8)."""

import json
import os

from app.config import parse_offline
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

MAX_PAPER_CHARS = 4000
MAX_ATTEMPTS = 3

_OFFLINE_SPEC_DATA = {
    "dataset": "offline-dataset",
    "estimator": "offline-estimator",
    "headline_numbers": {"estimate": 2.0, "p_value": 0.01},
    "significance_claim": "p < 0.05",
}


class ExtractionFailed(Exception):
    """Honest failure: model output could not become a valid spec."""


class Spec(BaseModel):
    """Falsifiable spec; extra model keys are ignored."""

    model_config = ConfigDict(extra="ignore")

    dataset: str = Field(min_length=1)
    estimator: str = Field(min_length=1)
    headline_numbers: dict[str, float] = Field(min_length=1)
    significance_claim: str = Field(min_length=1)

    @field_validator("dataset", "estimator", "significance_claim")
    @classmethod
    def _non_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


def build_prompt(paper_text: str, claim: str) -> str:
    """Demand exactly one JSON object with the four required keys."""
    paper = paper_text.strip()[:MAX_PAPER_CHARS]
    return (
        "Extract a falsifiable spec from the paper text and claim below.\n"
        "Return exactly one JSON object with keys "
        '"dataset", "estimator", "headline_numbers", "significance_claim" '
        "and no other prose. "
        '"headline_numbers" must map strings to numbers.\n'
        f"Paper:\n{paper}\n"
        f"Claim:\n{claim.strip()}\n"
        "JSON:"
    )


def parse_spec_json(raw: str) -> dict:
    """Validate raw model output into a JSON-serializable spec dict."""
    if not isinstance(raw, str) or not raw.strip():
        raise ExtractionFailed("empty model output")
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ExtractionFailed(f"invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ExtractionFailed("model output JSON is not an object")
    try:
        spec = Spec.model_validate(data)
    except ValidationError as exc:
        raise ExtractionFailed(f"spec validation failed: {exc}") from exc
    return spec.model_dump(mode="json")


def _fallback_complete(prompt: str, *args, **kwargs) -> str:
    raise ExtractionFailed("no LLM client available")


def _resolve_complete(complete_fn):
    if complete_fn is not None:
        return complete_fn
    try:
        from agent.llm import complete as llm_complete
    except ImportError:
        return _fallback_complete
    return llm_complete


def _offline_spec() -> dict:
    return Spec.model_validate(_OFFLINE_SPEC_DATA).model_dump(mode="json")


def extract(paper_text, claim, complete_fn=None) -> dict:
    """Turn paper prose plus a claim into a validated spec dict."""
    if not isinstance(paper_text, str) or not paper_text.strip():
        raise ExtractionFailed("paper_text must not be blank")
    if not isinstance(claim, str) or not claim.strip():
        raise ExtractionFailed("claim must not be blank")
    if parse_offline(os.environ.get("QED_OFFLINE")):
        return _offline_spec()
    complete = _resolve_complete(complete_fn)
    prompt = build_prompt(paper_text, claim)
    last_error: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            raw = complete(prompt)
        except ExtractionFailed as exc:
            last_error = exc
        except Exception as exc:  # noqa: BLE001 - any LLM error is a retry signal
            last_error = exc
        else:
            try:
                return parse_spec_json(raw)
            except ExtractionFailed as exc:
                last_error = exc
        if attempt < MAX_ATTEMPTS - 1:
            prompt = (
                f"Previous output was invalid: {last_error}. "
                "Return ONLY the JSON object with keys "
                '"dataset", "estimator", "headline_numbers", '
                '"significance_claim" and no prose.\n' + build_prompt(paper_text, claim)
            )
    raise ExtractionFailed(f"could not extract spec after {MAX_ATTEMPTS} attempts: {last_error}")
