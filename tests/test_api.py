from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

_VALID_VERDICTS = {"REPLICATED", "PARTIAL", "FAILED"}


def test_papers_lists_frozen_library():
    response = client.get("/api/papers")
    assert response.status_code == 200
    papers = response.json()
    assert isinstance(papers, list)
    assert len(papers) >= 4
    for paper in papers:
        assert paper["id"]
        assert paper["expected_verdict"] in _VALID_VERDICTS


def test_create_run_queued():
    response = client.post(
        "/api/runs", json={"paper_id": "demo_replicated", "claim": "test"}
    )
    assert response.status_code == 202
    body = response.json()
    assert body["run_id"].startswith("run_")
    assert body["status"] == "queued"

    detail = client.get(f"/api/runs/{body['run_id']}")
    assert detail.status_code == 200
    payload = detail.json()
    # Background worker advances queued -> running -> complete|failed; the
    # TestClient runs background tasks before returning, so the run may
    # already be complete on the first poll.
    assert payload["status"] in ("queued", "running", "complete", "failed")
    if payload["status"] == "complete":
        assert payload["verdict"] in _VALID_VERDICTS
    else:
        assert payload["verdict"] is None
    assert payload["trace"]


def test_create_run_unknown_paper_404_and_missing_field_422():
    unknown = client.post("/api/runs", json={"paper_id": "nope", "claim": "x"})
    assert unknown.status_code == 404
    assert unknown.status_code != 500

    missing = client.post("/api/runs", json={"claim": "x"})
    assert missing.status_code == 422
    assert missing.status_code != 500


def test_unknown_run_404_and_early_notebook_409():
    missing = client.get("/api/runs/run_deadbeef")
    assert missing.status_code == 404

    missing_notebook = client.get("/api/runs/run_deadbeef/notebook")
    assert missing_notebook.status_code == 404

    created = client.post(
        "/api/runs", json={"paper_id": "demo_replicated", "claim": "test"}
    )
    assert created.status_code == 202
    early = client.get(f"/api/runs/{created.json()['run_id']}/notebook")
    # The offline worker may already have completed the run, in which case
    # the notebook is 200; otherwise a pending run is 409. Either is correct.
    assert early.status_code in (200, 409)
