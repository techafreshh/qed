"""Typed stage events for the claim-to-verdict pipeline (issue #19).

Stdlib plus pydantic only: no network, no model calls, no file I/O,
no clock beyond a UTC timestamp helper, no randomness.
"""

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StageEvent(BaseModel):
    """One pipeline stage emission; ``detail`` carries the run log."""

    model_config = ConfigDict(extra="ignore")

    stage: str = Field(min_length=1)
    ts: str = Field(min_length=1)
    detail: dict = Field(default_factory=dict)

    @field_validator("stage", "ts")
    @classmethod
    def _non_blank(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("must not be blank")
        return value


def now_iso() -> str:
    """Current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def to_dict(event: StageEvent) -> dict:
    """Return a JSON-serializable dict for a stage event."""
    return event.model_dump(mode="json")
