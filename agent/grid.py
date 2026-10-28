"""Bounded analytical-choice grid planner (issue #9).

Pure functions only: no network, no model calls, no file I/O,
no clock, no randomness. Depends on the standard library plus
pydantic alone, so it runs offline on 3.12 and 3.13.
"""

import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_CELLS = 8
MIN_CELLS = 2


class GridCell(BaseModel):
    """One analytical choice; ``choice`` mirrors ``description``."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    controls: bool = False
    se_choice: str = "classical"
    sample_window: str = "full sample"
    choice: str = Field(default="")

    @field_validator("id", "description", "se_choice", "sample_window")
    @classmethod
    def _non_blank(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("must not be blank")
        return value

    @model_validator(mode="after")
    def _fill_choice(self) -> "GridCell":
        if not isinstance(self.choice, str) or not self.choice.strip():
            object.__setattr__(self, "choice", self.description)
        return self

    def __contains__(self, key: object) -> bool:
        return key in self.__pydantic_fields_set__ or key in type(self).model_fields

    def __getitem__(self, key: str) -> Any:
        fields = type(self).model_fields
        if key in fields:
            return getattr(self, key)
        raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default


def _coerce_to_dict(spec: Any) -> dict:
    """Best-effort coercion of a spec to a plain dict; never raises."""
    try:
        if spec is None:
            return {}
        if isinstance(spec, dict):
            return dict(spec)
        dump = getattr(spec, "model_dump", None)
        if callable(dump):
            try:
                data = dump()
            except TypeError:
                data = dump(mode="json")
            if isinstance(data, dict):
                return dict(data)
            return {}
        return {}
    except Exception:
        return {}


def _spec_text_blob(spec: Any, data: dict) -> str:
    """Lowercased text blob used only for window-name hints."""
    parts: list[str] = []
    try:
        parts.append(json.dumps(data, default=str, sort_keys=True))
    except Exception:
        pass
    try:
        parts.append(str(spec))
    except Exception:
        pass
    return "\n".join(parts).lower()


def _window_hint(text: str) -> tuple[str, str]:
    """Derive a deterministic (id slug, human label) window variant."""
    try:
        years = sorted(set(re.findall(r"\b(19\d{2}|20\d{2})\b", text or "")))
    except Exception:
        years = []
    if "2020" in years or "2020" in (text or ""):
        return "drop-2020", "excluding 2020"
    if "covid" in (text or "") or "pandemic" in (text or ""):
        return "drop-2020", "excluding 2020 (Covid period)"
    if years:
        year = years[-1]
        return f"drop-{year}", f"excluding {year}"
    return "exclude-tail", "excluding the tail period"


def _make_cell(
    cell_id: str,
    description: str,
    controls: bool,
    se_choice: str,
    sample_window: str,
) -> GridCell:
    return GridCell(
        id=cell_id,
        description=description,
        controls=controls,
        se_choice=se_choice,
        sample_window=sample_window,
        choice=description,
    )


def plan_grid(spec: Any) -> list[GridCell]:
    """Plan a bounded grid of analytical choices for a spec.

    Accepts the ``extract`` output shape (dict with ``dataset`` /
    ``estimator`` / ``headline_numbers`` / ``significance_claim``) plus
    any ragged dict, ``Spec``-like object with ``model_dump``, or
    ``None``. Never raises on input shape; always returns between 2
    and 8 cells (hard-truncated to ``MAX_CELLS``) with unique ids, in
    deterministic priority order: baseline, one-axis variants, then
    two-way combos.
    """
    try:
        data = _coerce_to_dict(spec)
        text = _spec_text_blob(spec, data)
        slug, label = _window_hint(text)
        window_id = f"window-{slug}"
        combo_window_id = f"controls-in-{window_id}"
        window_sample = label
        combo_window_sample = label

        cells = [
            _make_cell(
                "baseline",
                "Baseline OLS with no additional controls, classical standard errors, and full sample.",
                False,
                "classical",
                "full sample",
            ),
            _make_cell(
                "controls-in",
                "OLS with additional controls included, classical standard errors, and full sample.",
                True,
                "classical",
                "full sample",
            ),
            _make_cell(
                "se-robust",
                "OLS with no additional controls, heteroskedasticity-robust (HC1) standard errors, and full sample.",
                False,
                "HC1",
                "full sample",
            ),
            _make_cell(
                window_id,
                f"OLS with no additional controls, classical standard errors, and {label} sample window.",
                False,
                "classical",
                window_sample,
            ),
            _make_cell(
                "controls-in-se-robust",
                "OLS with additional controls included and heteroskedasticity-robust (HC1) standard errors on the full sample.",
                True,
                "HC1",
                "full sample",
            ),
            _make_cell(
                combo_window_id,
                f"OLS with additional controls included, classical standard errors, and {label} sample window.",
                True,
                "classical",
                combo_window_sample,
            ),
        ]

        seen: set[str] = set()
        unique: list[GridCell] = []
        for cell in cells:
            if cell.id in seen:
                continue
            seen.add(cell.id)
            unique.append(cell)
        cells = unique[:MAX_CELLS]

        counter = 1
        while len(cells) < MIN_CELLS:
            fallback_id = f"generic-{counter}"
            if fallback_id not in seen:
                cells.append(
                    _make_cell(
                        fallback_id,
                        f"Generic robustness check {counter}: OLS with no additional controls, classical standard errors, and full sample.",
                        False if counter % 2 == 1 else True,
                        "classical",
                        "full sample",
                    )
                )
                seen.add(fallback_id)
            counter += 1
        return cells
    except Exception:
        return [
            _make_cell(
                "baseline",
                "Baseline OLS with no additional controls, classical standard errors, and full sample.",
                False,
                "classical",
                "full sample",
            ),
            _make_cell(
                "controls-in",
                "OLS with additional controls included, classical standard errors, and full sample.",
                True,
                "classical",
                "full sample",
            ),
        ]
