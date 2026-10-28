"""Offline acceptance tests for the library manifest schema (issue #5)."""

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from library.schema import PaperManifest, load_library, load_manifest

PAPERS_DIR = Path(__file__).resolve().parent.parent / "library" / "papers"


def _valid_payload() -> dict:
    return {
        "id": "example_replication",
        "citation": "Smith, J. et al. (2015). Example study.",
        "claim": "Smaller classes raise scores by ~5 points.",
        "dataset_url": "https://example.org/datasets/class_size_scores.csv",
        "sha256": "0" * 64,
        "license": "CC0-1.0",
        "estimator": "OLS with school controls",
        "reported_numbers": {"headline_estimate": 5.0, "p_value": 0.01},
        "expected_verdict": "REPLICATED",
        "source": "Reproducibility Project: Psychology",
    }


def _write_yaml(tmp_path: Path, name: str, payload: dict) -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return path


def test_valid_manifest_parses_with_verdict_in_domain(tmp_path):
    path = _write_yaml(tmp_path, "valid.yaml", _valid_payload())
    manifest = load_manifest(path)
    assert isinstance(manifest, PaperManifest)
    assert manifest.expected_verdict in ("REPLICATED", "PARTIAL", "FAILED")


def test_missing_dataset_url_raises_validation_error(tmp_path):
    payload = _valid_payload()
    del payload["dataset_url"]
    path = _write_yaml(tmp_path, "missing_url.yaml", payload)
    with pytest.raises(ValidationError):
        load_manifest(path)


def test_invalid_verdict_raises_validation_error(tmp_path):
    payload = _valid_payload()
    payload["expected_verdict"] = "UNKNOWN"
    path = _write_yaml(tmp_path, "bad_verdict.yaml", payload)
    with pytest.raises(ValidationError):
        load_manifest(path)


def test_load_library_picks_up_checked_in_example():
    manifests = load_library(PAPERS_DIR)
    assert manifests
    by_id = {m.id: m for m in manifests}
    assert "example_replication" in by_id
    assert by_id["example_replication"].expected_verdict in (
        "REPLICATED",
        "PARTIAL",
        "FAILED",
    )
