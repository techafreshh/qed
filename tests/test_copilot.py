"""CopilotKit AG-UI side-chat acceptance tests (issue #23).

Black-box TestClient probes plus UI source-grep assertions, mirroring
tests/test_ui_shell.py. Credential-free: QED_OFFLINE=1, no subprocess.
"""
from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _offline(monkeypatch):
    monkeypatch.setenv("QED_OFFLINE", "1")
    for key in ("META_API_KEY", "META_API_URL", "MODAL_TOKEN"):
        monkeypatch.delenv(key, raising=False)


def _post_and_wait(paper_id="demo_replicated", claim="wages rise", timeout=10.0):
    response = client.post("/api/runs", json={"paper_id": paper_id, "claim": claim})
    assert response.status_code == 202
    run_id = response.json()["run_id"]
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


def test_events_stream_contains_agui_markers_for_chat(monkeypatch):
    _offline(monkeypatch)
    run_id, payload = _post_and_wait()
    assert payload["status"] == "complete"
    stream = client.get(
        f"/api/runs/{run_id}/events", headers={"Accept": "text/event-stream"}
    )
    assert stream.status_code == 200
    assert "TEXT_MESSAGE_CONTENT" in stream.text
    assert "TOOL_CALL_START" in stream.text


def test_copilot_source_wiring():
    source = (REPO_ROOT / "ui" / "src" / "copilot.tsx").read_text(encoding="utf-8")
    assert "useCopilotChat" in source
    assert "prompt-input" in source
    assert "message-scroller" in source
    assert "message" in source
    assert "/api/runs/" in source


def test_verdict_fallback_without_copilotkit(monkeypatch):
    _offline(monkeypatch)
    response = client.get("/")
    assert response.status_code == 200
    assert '<div id="root"' in response.text
    verdict_view = (REPO_ROOT / "ui" / "src" / "views" / "VerdictCard.tsx").read_text(
        encoding="utf-8"
    )
    assert "copilotkit" not in verdict_view.lower()
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "fallback" in readme.lower()
    assert "REST" in readme or "rest" in readme.lower()
