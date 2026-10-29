"""Replay-gate acceptance tests (issue #26).

Credential-free: scrubbed env with ``QED_OFFLINE=1`` and a forbidden
``subprocess`` prove zero egress and zero credit spend. All tests call
``evals.replay.main()`` in-process (no subprocess) so the suite stays
under seconds, guarding the 120s wall-clock budget at unit level.
"""

import re
import shutil
import subprocess
import time
from pathlib import Path

import yaml

from evals.replay import main

PAPERS_DIR = Path(__file__).resolve().parent.parent / "library" / "papers"
FIXTURES = {"example.yaml"}


def _scrubbed_env(monkeypatch, **overrides):
    for key in (
        "META_API_KEY",
        "META_API_URL",
        "MODAL_TOKEN",
        "QED_OFFLINE",
        "QED_CODEGEN_BACKEND",
        "OPENCODE_INVOKED_BY",
        "QED_AGENT_DEPTH",
    ):
        monkeypatch.delenv(key, raising=False)
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)


def _forbid_subprocess(monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("subprocess must not run offline")

    for name in ("Popen", "run", "call", "check_call", "check_output"):
        monkeypatch.setattr(subprocess, name, _boom)


def _frozen_names() -> list[str]:
    return sorted(
        p.name for p in PAPERS_DIR.glob("*.yaml") if p.name not in FIXTURES
    )


def _copy_library(tmp_path: Path) -> Path:
    for path in PAPERS_DIR.glob("*.yaml"):
        shutil.copy(path, tmp_path / path.name)
    return tmp_path


def test_replay_full_library_matches(monkeypatch, capsys):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    _forbid_subprocess(monkeypatch)
    start = time.monotonic()
    assert main([]) == 0
    assert time.monotonic() - start < 60
    out = capsys.readouterr().out
    match = re.search(r"(\d+)/(\d+) match", out)
    assert match is not None, out
    assert match.group(1) == match.group(2)
    assert int(match.group(1)) >= 4


def test_replay_tampered_fixture_mismatches(monkeypatch, capsys, tmp_path):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    _forbid_subprocess(monkeypatch)
    papers_dir = _copy_library(tmp_path)
    target = papers_dir / _frozen_names()[0]
    doc = yaml.safe_load(target.read_text(encoding="utf-8"))
    flipped = "FAILED" if doc["expected_verdict"] != "FAILED" else "REPLICATED"
    doc["expected_verdict"] = flipped
    target.write_text(yaml.safe_dump(doc), encoding="utf-8")
    assert main(["--papers-dir", str(papers_dir)]) != 0
    capsys.readouterr()
    paper_id = yaml.safe_load(target.read_text(encoding="utf-8"))["id"]
    assert (
        main(["--papers-dir", str(papers_dir), "--paper", paper_id]) != 0
    )


def test_replay_single_paper_filter(monkeypatch, capsys):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    _forbid_subprocess(monkeypatch)
    paper_id = yaml.safe_load(
        (PAPERS_DIR / _frozen_names()[0]).read_text(encoding="utf-8")
    )["id"]
    assert main(["--paper", paper_id]) == 0
    out = capsys.readouterr().out
    assert "1/1 match" in out


def test_replay_unknown_paper_errors(monkeypatch, capsys):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    _forbid_subprocess(monkeypatch)
    assert main(["--paper", "no_such_paper_xyz"]) == 2
    capsys.readouterr()
    assert main(["--paper", "../card_krueger_1994_minwage"]) == 2
