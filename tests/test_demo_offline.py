"""Offline demo-mode acceptance tests (issue #25).

Credential-free: scrubbed env with ``QED_OFFLINE=1`` and a forbidden
``subprocess`` prove both demo papers complete offline with zero egress.
Also asserts the rehearsed ``make demo-offline`` entry point exists.
"""
import subprocess
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

_MAKEFILE = Path(__file__).resolve().parent.parent / "Makefile"


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


def _post_and_wait(paper_id, claim="wages rise", timeout=10.0):
    response = client.post("/api/runs", json={"paper_id": paper_id, "claim": claim})
    assert response.status_code == 202
    run_id = response.json()["run_id"]
    deadline = time.monotonic() + timeout
    detail = None
    while time.monotonic() < deadline:
        probe = client.get(f"/api/runs/{run_id}")
        assert probe.status_code == 200
        detail = probe.json()
        if detail["status"] == "complete":
            break
        time.sleep(0.05)
    assert detail is not None
    return detail


def test_demo_replicated_verdict_offline(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    _forbid_subprocess(monkeypatch)
    detail = _post_and_wait("demo_replicated")
    assert detail["status"] == "complete"
    assert detail["verdict"] == "REPLICATED"


def test_demo_failed_verdict_and_fragile_choice_offline(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    _forbid_subprocess(monkeypatch)
    detail = _post_and_wait("demo_failed")
    assert detail["status"] == "complete"
    assert detail["verdict"] == "FAILED"
    assert isinstance(detail["fragile_choice"], str) and detail["fragile_choice"].strip()


def test_demo_offline_makefile_target(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    _forbid_subprocess(monkeypatch)
    text = _MAKEFILE.read_text(encoding="utf-8")
    assert "demo-offline:" in text
    assert "QED_OFFLINE=1" in text
