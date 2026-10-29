"""Adversarial honest-refusal probe tests (issue #27).

Credential-free: scrubbed env with ``QED_OFFLINE=1``. Subprocess is
forbidden for the pure refusal tests; the overtime probe and the CLI
test need subprocess (fake sandbox, CLI spawn) so they only scrub
credentials instead.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from evals.probes import (
    probe_excluded_dependency,
    probe_missing_file,
    probe_overtime_run,
    probe_underspecified_claim,
)

client = TestClient(app)

_REPO_ROOT = Path(__file__).resolve().parent.parent


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


def _assert_refusal(result, name):
    assert result["name"] == name
    assert result["outcome"] in ("refused", "degraded")
    assert isinstance(result["reason"], str) and result["reason"].strip()


def test_missing_file_refused(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    _forbid_subprocess(monkeypatch)
    _assert_refusal(probe_missing_file(), "missing_file")


def test_missing_file_emits_no_verdict_numbers(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    _forbid_subprocess(monkeypatch)
    result = probe_missing_file()
    assert result["outcome"] == "refused"
    blob = json.dumps(result)
    assert "REPLICATED" not in blob
    assert "PARTIAL" not in blob
    assert "FAILED" not in blob
    assert not re.search(r"\d+\.\d+", blob)


def test_underspecified_claim_refused(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    _forbid_subprocess(monkeypatch)
    _assert_refusal(probe_underspecified_claim(), "underspecified_claim")


def test_underspecified_claim_422_never_500(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    _forbid_subprocess(monkeypatch)
    response = client.post(
        "/api/runs", json={"paper_id": "demo_replicated", "claim": "it works"}
    )
    assert response.status_code == 422
    assert response.status_code != 500
    assert "detail" in response.json()


def test_excluded_dependency_refused(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    _forbid_subprocess(monkeypatch)
    _assert_refusal(probe_excluded_dependency(), "excluded_dependency")


def test_overtime_run_degraded(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    _assert_refusal(probe_overtime_run(), "overtime_run")


def test_probes_cli_offline(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    import os

    clean = {k: v for k, v in os.environ.items()
             if k not in ("META_API_KEY", "META_API_URL", "MODAL_TOKEN",
                          "QED_CODEGEN_BACKEND")}
    clean["QED_OFFLINE"] = "1"
    proc = subprocess.run(
        [sys.executable, "evals/probes.py", "--offline"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
        env=clean,
    )
    assert proc.returncode == 0, proc.stderr
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    assert len(lines) == 4
    for line in lines:
        assert "PASS" in line
