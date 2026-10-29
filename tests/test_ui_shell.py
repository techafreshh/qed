from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_root_serves_ui_shell():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert '<div id="root"' in response.text
    assert "QED" in response.text


def test_static_index_bundle_exists():
    index = REPO_ROOT / "app" / "static" / "index.html"
    assert index.is_file()
    text = index.read_text(encoding="utf-8")
    assert '<div id="root"' in text
    assert "QED" in text


def test_verdict_card_imports_beui():
    view = REPO_ROOT / "ui" / "src" / "views" / "VerdictCard.tsx"
    assert view.is_file()
    assert "beUI" in view.read_text(encoding="utf-8")


def test_unknown_non_api_path_falls_back_to_spa():
    response = client.get("/runs/some-run-id/verdict")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "QED" in response.text


def test_unknown_api_path_stays_404_json():
    response = client.get("/api/runs/does-not-exist")
    assert response.status_code == 404


def test_claim_input_posts_form_to_runs_with_paper_text():
    view = REPO_ROOT / "ui" / "src" / "views" / "ClaimInput.tsx"
    assert view.is_file()
    text = view.read_text(encoding="utf-8")
    assert "<form" in text
    assert "/api/runs" in text
    assert "paper_text" in text
    assert "<textarea" in text
    assert "<select" in text
