"""Validated manifest contract for frozen library papers (PRD section 10).

Each paper under ``library/papers/*.yaml`` records its dataset URL + sha256 +
license, estimator spec, reported numbers, and expected verdict + source, so
later replay and sourcing laps have a deterministic target to reproduce
against. Loading is offline and credential-free.
"""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

VerdictLabel = Literal["REPLICATED", "PARTIAL", "FAILED"]

_DEFAULT_PAPERS_DIR = Path(__file__).resolve().parent / "papers"


class PaperManifest(BaseModel):
    """Frozen-paper manifest; all ten fields required, extras forbidden."""

    model_config = ConfigDict(extra="forbid")

    id: str
    citation: str
    claim: str
    dataset_url: HttpUrl
    sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    license: str
    estimator: str
    reported_numbers: dict[str, float]
    expected_verdict: VerdictLabel
    source: str


def load_manifest(path: str | Path) -> PaperManifest:
    """Parse one manifest YAML file into a validated ``PaperManifest``.

    Missing keys, bad verdict strings, and malformed hashes/URLs raise
    ``pydantic.ValidationError`` unchanged.
    """
    text = Path(path).read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    return PaperManifest.model_validate(data)


def load_library(directory: str | Path | None = None) -> list[PaperManifest]:
    """Validate every ``*.yaml`` manifest in ``directory`` (sorted by name)."""
    papers_dir = Path(directory) if directory is not None else _DEFAULT_PAPERS_DIR
    return [
        load_manifest(path)
        for path in sorted(papers_dir.glob("*.yaml"))
        if path.is_file()
    ]
