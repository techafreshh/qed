"""Offline background-worker acceptance tests (issue #21).

Credential-free: TestClient black-box, QED_OFFLINE=1, no subprocess, no
network. The offline orchestrator stub completes in milliseconds, so the
background task finishes before the 10s poll budget expires.
"""
from __future__ import annotations

import subprocess
import time

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

_VALID_VERDICTS = {"REPLICATED", "PARTIAL", "FAILED"}


def _offline(monkeypatch):
    monkeypatch.setenv("QED_OFFLINE", "1")
    for key in ("META_API_KEY", "META_API_URL", "MODAL_TOKEN"):
        monkeypatch.delenv(key, raising=False)


def _forbid_subprocess(monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("subprocess must not run offline")

    for name in ("Popen", "run", "call", "check_call", "check_output"):
        monkeypatch.setattr(subprocess, name, _boom)


def _post_and_wait(paper_id="demo_replicated", claim="wages rise", timeout=10.0):
    response = client.post("/api/runs", json={"paper_id": paper_id, "claim": claim})
    assert response.status_code == 202
    body = response.json()
    assert body["run_id"].startswith("run_")
    assert body["status"] == "queued"
    run_id = body["run_id"]
    deadline = time.monotonic() + timeout
    last: dict | None = None
    while time.monotonic() < deadline:
        detail = client.get(f"/api/runs/{run_id}")
        assert detail.status_code == 200
        last = detail.json()
        if last["status"] == "complete" and last["verdict"] is not None:
            break
        if last["status"] == "failed":
            break
        time.sleep(0.05)
    assert last is not None
    return run_id, last


def test_post_completes_within_10s_offline(monkeypatch):
    _offline(monkeypatch)
    _forbid_subprocess(monkeypatch)
    run_id, payload = _post_and_wait()
    assert payload["status"] == "complete"
    assert payload["verdict"] in _VALID_VERDICTS
    assert payload["run_id"] == run_id


def test_events_stream_contains_agui_markers(monkeypatch):
    _offline(monkeypatch)
    _forbid_subprocess(monkeypatch)
    run_id, payload = _post_and_wait()
    assert payload["status"] == "complete"
    stream = client.get(
        f"/api/runs/{run_id}/events", headers={"Accept": "text/event-stream"}
    )
    assert stream.status_code == 200
    assert "text/event-stream" in stream.headers.get("content-type", "")
    body = stream.text
    assert "RUN_STARTED" in body
    assert "RUN_FINISHED" in body
    assert "TEXT_MESSAGE_CONTENT" in body
    assert "TOOL_CALL_START" in body
    assert "TOOL_CALL_RESULT" in body


def test_events_unknown_id_404(monkeypatch):
    _offline(monkeypatch)
    response = client.get(
        "/api/runs/run_deadbeef/events", headers={"Accept": "text/event-stream"}
    )
    assert response.status_code == 404


def test_worker_marks_failed_honestly(monkeypatch):
    _offline(monkeypatch)
    _forbid_subprocess(monkeypatch)
    import agent.orchestrate as orchestrate

    def _boom(paper_id, claim="", backend=None):
        raise RuntimeError("synthetic orchestrator failure")

    monkeypatch.setattr(orchestrate, "run_claim", _boom)
    response = client.post(
        "/api/runs", json={"paper_id": "demo_replicated", "claim": "will fail"}
    )
    assert response.status_code == 202
    run_id = response.json()["run_id"]
    deadline = time.monotonic() + 10.0
    last: dict | None = None
    while time.monotonic() < deadline:
        detail = client.get(f"/api/runs/{run_id}")
        assert detail.status_code == 200
        assert detail.status_code != 500
        last = detail.json()
        if last["status"] == "failed":
            break
        time.sleep(0.05)
    assert last is not None
    assert last["status"] == "failed"
    assert last["verdict"] == "FAILED"
    events = client.get(
        f"/api/runs/{run_id}/events", headers={"Accept": "text/event-stream"}
    )
    assert events.status_code in (200, 404)
    assert events.status_code != 500
    missing = client.get("/api/runs/run_deadbeef")
    assert missing.status_code == 404
