"""Completed-demo-run probe entrypoint (issue #29).

Drives one ``demo_replicated`` run through the TestClient stack and
asserts the acceptance probe chain — ``GET /health``, ``GET
/api/papers``, ``POST /api/runs``, ``GET /api/runs/{id}``, ``GET
/api/runs/{id}/notebook``, ``GET /api/runs/{id}/events`` — returns
200, 200, 202, 200, 200, 200 for a completed run. Credential-free: no
network, no subprocess — safe under ``QED_OFFLINE=1`` with no keys.
Exit 0 iff the full chain passes.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

os.environ.setdefault("QED_OFFLINE", "1")

_POLL_TIMEOUT_S = 10.0


def _fail(message: str) -> int:
    print("demo-offline FAIL: %s" % message, file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    del argv  # the probe always covers the fixed acceptance chain
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)

    health = client.get("/health")
    if health.status_code != 200:
        return _fail("GET /health -> %s (want 200)" % health.status_code)

    papers = client.get("/api/papers")
    if papers.status_code != 200:
        return _fail("GET /api/papers -> %s (want 200)" % papers.status_code)

    created = client.post(
        "/api/runs",
        json={"paper_id": "demo_replicated", "claim": "wages rise"},
    )
    if created.status_code != 202:
        return _fail("POST /api/runs -> %s (want 202)" % created.status_code)
    run_id = created.json().get("run_id", "")

    detail = None
    deadline = time.monotonic() + _POLL_TIMEOUT_S
    while time.monotonic() < deadline:
        probe = client.get("/api/runs/%s" % run_id)
        if probe.status_code != 200:
            return _fail(
                "GET /api/runs/{id} -> %s (want 200)" % probe.status_code
            )
        detail = probe.json()
        if detail.get("status") == "complete":
            break
        time.sleep(0.05)
    if not detail or detail.get("status") != "complete":
        return _fail("run %s never completed" % run_id)

    notebook = client.get("/api/runs/%s/notebook" % run_id)
    if notebook.status_code != 200:
        return _fail(
            "GET /api/runs/{id}/notebook -> %s (want 200)"
            % notebook.status_code
        )
    if not isinstance(notebook.json().get("cells"), list):
        return _fail("notebook has no cells list")

    events = client.get("/api/runs/%s/events" % run_id)
    if events.status_code != 200:
        return _fail(
            "GET /api/runs/{id}/events -> %s (want 200)" % events.status_code
        )

    print(
        "demo-offline PASS: 200,200,202,200,200,200 run %s verdict %s"
        % (run_id, detail.get("verdict"))
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
