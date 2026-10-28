"""Offline acceptance tests for the frozen paper library (issue #6).

No network, no credentials: validates the manifests frozen under
``library/papers/`` — freeze count, verdict mix, required fields, and
conformance to the ``library.schema`` contract. The checked-in
``example.yaml`` is a schema placeholder fixture, not a frozen paper, so it
is excluded from the freeze scope (it stays covered by
``test_library_schema.py``).
"""

import re
from pathlib import Path

import pytest
import yaml

from library.schema import load_library, load_manifest

PAPERS_DIR = Path(__file__).resolve().parent.parent / "library" / "papers"
FIXTURES = {"example.yaml"}
REQUIRED_NONEMPTY = (
    "dataset_url",
    "sha256",
    "license",
    "estimator",
    "reported_numbers",
    "source",
)
SHA_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def frozen_paths() -> list[Path]:
    return sorted(
        p for p in PAPERS_DIR.glob("*.yaml") if p.is_file() and p.name not in FIXTURES
    )


def frozen_docs() -> list[dict]:
    return [yaml.safe_load(p.read_text(encoding="utf-8")) for p in frozen_paths()]


def test_freeze_count_at_least_four():
    assert len(frozen_paths()) >= 4


def test_verdict_mix_failure_and_replicates():
    verdicts = [d["expected_verdict"] for d in frozen_docs()]
    assert sum(v == "FAILED" for v in verdicts) >= 1
    assert sum(v == "REPLICATED" for v in verdicts) >= 2


def test_required_fields_nonempty():
    for path, doc in zip(frozen_paths(), frozen_docs()):
        for field in REQUIRED_NONEMPTY:
            value = doc.get(field)
            assert value not in (None, "", {}, []), f"{path.name}: {field} is empty"
        assert str(doc.get("id", "")).strip(), f"{path.name}: id is empty"
        assert str(doc.get("citation", "")).strip(), f"{path.name}: citation is empty"
        assert str(doc.get("claim", "")).strip(), f"{path.name}: claim is empty"
        assert doc.get("expected_verdict") in (
            "REPLICATED",
            "PARTIAL",
            "FAILED",
        ), f"{path.name}: bad verdict"


def test_sha256_is_pinned_hex():
    for path, doc in zip(frozen_paths(), frozen_docs()):
        assert SHA_RE.match(str(doc.get("sha256", ""))), f"{path.name}: bad sha256"


def test_frozen_manifests_validate_against_schema():
    manifests = [load_manifest(p) for p in frozen_paths()]
    assert len(manifests) == len(frozen_paths())
    ids = [m.id for m in manifests]
    assert len(set(ids)) == len(ids), "duplicate manifest ids"


def test_load_library_covers_freeze():
    by_id = {m.id for m in load_library(PAPERS_DIR)}
    for manifest in (load_manifest(p) for p in frozen_paths()):
        assert manifest.id in by_id
