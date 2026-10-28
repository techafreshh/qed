"""Credential-free persistence tests (stdlib sqlite3 + tmp_path only)."""
import sqlite3

from db.models import (
    DEFAULT_DB_PATH,
    create_run,
    get_run,
    init_db,
    insert_artifact,
    insert_paper,
    list_artifacts,
    list_papers,
)


def test_default_db_path_is_data_qed_db():
    assert str(DEFAULT_DB_PATH) == "data/qed.db"


def test_create_and_fetch_run(tmp_path):
    db_path = tmp_path / "qed.db"
    run = create_run("paper-1", db_path=db_path)
    assert run["run_id"].startswith("run_")
    assert run["status"] == "queued"

    fetched = get_run(run["run_id"], db_path=db_path)
    assert fetched is not None
    assert fetched["run_id"] == run["run_id"]
    assert fetched["status"] == "queued"
    assert fetched["run_id"].startswith("run_")
    assert db_path.exists()


def test_get_run_unknown_id_returns_none(tmp_path):
    assert get_run("run_missing", db_path=tmp_path / "qed.db") is None


def test_insert_and_list_papers(tmp_path):
    db_path = tmp_path / "qed.db"
    before = list_papers(db_path=db_path)
    row = insert_paper(
        "paper-1",
        title="Minimal effects",
        claim="A 10% rise cuts employment 1-3%.",
        source="frozen-library",
        db_path=db_path,
    )
    after = list_papers(db_path=db_path)
    assert len(after) == len(before) + 1
    assert row["id"] in {paper["id"] for paper in after}


def test_insert_paper_mapping_and_artifacts_round_trip(tmp_path):
    db_path = tmp_path / "qed.db"
    insert_paper({"id": "paper-9", "title": "Mapped", "claim": "c", "source": "s"},
                 db_path=db_path)
    ids = {paper["id"] for paper in list_papers(db_path=db_path)}
    assert "paper-9" in ids

    run = create_run("paper-9", db_path=db_path)
    artifact = insert_artifact(run["run_id"], "notebook", "runs/nb.ipynb",
                              db_path=db_path)
    assert artifact["run_id"] == run["run_id"]
    listed = list_artifacts(run["run_id"], db_path=db_path)
    assert [item["id"] for item in listed] == [artifact["id"]]


def test_init_db_is_idempotent_and_preserves_rows(tmp_path):
    db_path = tmp_path / "qed.db"
    run = create_run("paper-1", db_path=db_path)
    insert_paper("paper-1", db_path=db_path)

    init_db(db_path)
    with sqlite3.connect(str(db_path)) as conn:
        init_db(conn)

    assert get_run(run["run_id"], db_path=db_path)["status"] == "queued"
    assert "paper-1" in {paper["id"] for paper in list_papers(db_path=db_path)}


def test_fresh_nested_db_path_is_created(tmp_path):
    db_path = tmp_path / "nested" / "qed.db"
    assert not db_path.exists()
    run = create_run("paper-1", db_path=db_path)
    assert db_path.exists()
    assert get_run(run["run_id"], db_path=db_path) is not None
