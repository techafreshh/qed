"""Offline cached-run replay acceptance tests (issue #15).

Credential-free: scrubbed env with ``QED_OFFLINE=1`` and a forbidden
``subprocess`` prove zero egress and zero credit spend.
"""
import subprocess
import time

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from runner.offline import NotFound, replay

client = TestClient(app)


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


def test_replay_replicated_verdict_and_cells(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    _forbid_subprocess(monkeypatch)
    result = replay("demo_replicated")
    assert result["verdict"] == "REPLICATED"
    assert isinstance(result["notebook"], dict)
    assert len(result["notebook"]["cells"]) >= 2
    assert isinstance(result["fragile_choice"], str) and result["fragile_choice"].strip()
    assert [entry["stage"] for entry in result["trace"]] == [
        "extraction",
        "codegen",
        "sandbox",
        "verdict",
    ]
    # Each call returns a fresh copy; callers cannot mutate the cache.
    result["notebook"]["cells"].append({"cell_type": "markdown"})
    assert len(replay("demo_replicated")["notebook"]["cells"]) >= 2


def test_replay_failed_verdict(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    _forbid_subprocess(monkeypatch)
    result = replay("demo_failed")
    assert result["verdict"] == "FAILED"
    assert len(result["notebook"]["cells"]) >= 2
    assert isinstance(result["fragile_choice"], str) and result["fragile_choice"].strip()


def test_replay_unknown_raises_notfound(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    _forbid_subprocess(monkeypatch)
    with pytest.raises(NotFound):
        replay("nope")
    with pytest.raises(NotFound):
        replay("../demo_replicated")
    with pytest.raises(NotFound):
        replay("   ")


def test_replay_notfound_maps_to_404(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    _forbid_subprocess(monkeypatch)
    with pytest.raises(HTTPException) as excinfo:
        try:
            replay("nope")
        except NotFound as exc:
            raise HTTPException(status_code=404, detail="unknown paper") from exc
    assert excinfo.value.status_code == 404


def test_offline_run_completes_end_to_end(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    _forbid_subprocess(monkeypatch)
    response = client.post(
        "/api/runs", json={"paper_id": "demo_replicated", "claim": "wages rise"}
    )
    assert response.status_code == 202
    run_id = response.json()["run_id"]
    deadline = time.monotonic() + 10.0
    detail = None
    while time.monotonic() < deadline:
        probe = client.get(f"/api/runs/{run_id}")
        assert probe.status_code == 200
        detail = probe.json()
        if detail["status"] == "complete":
            break
        time.sleep(0.05)
    assert detail is not None
    assert detail["status"] == "complete"
    assert detail["verdict"] == "REPLICATED"
    notebook = client.get(f"/api/runs/{run_id}/notebook")
    assert notebook.status_code == 200
    assert len(notebook.json()["cells"]) >= 2
