"""SQLite persistence for papers, runs, and artifacts (stdlib sqlite3 only)."""
from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB_PATH = Path("data/qed.db")

_SCHEMA_STATEMENTS = (
    """CREATE TABLE IF NOT EXISTS papers (
        id TEXT PRIMARY KEY,
        title TEXT,
        claim TEXT,
        source TEXT,
        created_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS runs (
        run_id TEXT PRIMARY KEY,
        paper_id TEXT,
        status TEXT NOT NULL DEFAULT 'queued',
        verdict TEXT,
        created_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS artifacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL REFERENCES runs(run_id),
        kind TEXT,
        path TEXT,
        created_at TEXT
    )""",
)

_DB_SUFFIXES = (".db", ".sqlite3")


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _resolve_path(db_path: str | Path | None) -> Path:
    """Resolve a DB path; bare relative paths anchor at the repo root."""
    if db_path is None:
        return _repo_root() / DEFAULT_DB_PATH
    candidate = Path(db_path)
    if candidate.is_absolute():
        return candidate
    if candidate.parts and candidate.parts[0] == "data":
        return _repo_root() / candidate
    return _repo_root() / candidate


def _looks_like_db_path(value: object) -> bool:
    if isinstance(value, Path):
        return True
    return (
        isinstance(value, str)
        and (value.endswith(_DB_SUFFIXES) or os.sep in value or "/" in value)
    )


def _open(db_path: str | Path | None) -> sqlite3.Connection:
    resolved = _resolve_path(db_path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(resolved))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    conn = _open(db_path)
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection | str | Path | None = None, db_path=None) -> None:
    """Create tables idempotently; accepts a connection, a path, or nothing."""
    if isinstance(conn, (str, Path)):
        db_path = conn if db_path is None else db_path
        conn = None
    if conn is None:
        with _open(db_path) as fresh:
            for statement in _SCHEMA_STATEMENTS:
                fresh.execute(statement)
            fresh.commit()
        return
    for statement in _SCHEMA_STATEMENTS:
        conn.execute(statement)
    try:
        conn.commit()
    except sqlite3.Error:
        pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_run(paper_id: str | None = "", db_path=None, **kwargs) -> dict:
    """Insert a queued run row and return it as a dict."""
    if db_path is None and "db_path" in kwargs:
        db_path = kwargs.pop("db_path")
    status = kwargs.pop("status", "queued")
    verdict = kwargs.pop("verdict", None)
    # Tolerate a mapping passed positionally instead of a paper id.
    if isinstance(paper_id, dict):
        payload = dict(paper_id)
        paper_id = payload.get("paper_id", payload.get("id", ""))
        status = payload.get("status", status)
        verdict = payload.get("verdict", verdict)
    run_id = kwargs.pop("run_id", None) or f"run_{uuid.uuid4().hex[:8]}"
    created_at = _now_iso()
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO runs (run_id, paper_id, status, verdict, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (run_id, paper_id, status, verdict, created_at),
        )
        conn.commit()
        row = conn.execute(
            "SELECT run_id, paper_id, status, verdict, created_at"
            " FROM runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
    return dict(row)


def get_run(run_id: str, db_path=None, **kwargs) -> dict | None:
    """Fetch a run row by id; return None when unknown."""
    if db_path is None and "db_path" in kwargs:
        db_path = kwargs["db_path"]
    if not isinstance(run_id, str):
        return None
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT run_id, paper_id, status, verdict, created_at"
            " FROM runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
    return dict(row) if row is not None else None


def insert_paper(
    paper_id: str | dict | None = None,
    title: str = "",
    claim: str = "",
    source: str = "",
    db_path=None,
    **kwargs,
) -> dict:
    """Insert a paper row (id string or mapping) and return it as a dict."""
    if isinstance(paper_id, dict):
        payload = dict(paper_id)
        if db_path is None and _looks_like_db_path(title):
            db_path = title
        paper_id = payload.get("id", payload.get("paper_id"))
        title = payload.get("title", "")
        claim = payload.get("claim", "")
        source = payload.get("source", "")
    if paper_id is None:
        paper_id = kwargs.pop("id", kwargs.pop("paper_id", None))
    if db_path is None and "db_path" in kwargs:
        db_path = kwargs.pop("db_path")
    created_at = _now_iso()
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO papers (id, title, claim, source, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (paper_id, title, claim, source, created_at),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, title, claim, source, created_at"
            " FROM papers WHERE id = ?",
            (paper_id,),
        ).fetchone()
    return dict(row)


def list_papers(db_path=None, **kwargs) -> list[dict]:
    """List all paper rows as dicts in insertion order."""
    if db_path is None and "db_path" in kwargs:
        db_path = kwargs["db_path"]
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, title, claim, source, created_at"
            " FROM papers ORDER BY rowid"
        ).fetchall()
    return [dict(row) for row in rows]


def insert_artifact(
    run_id: str | dict,
    kind: str = "",
    path: str = "",
    db_path=None,
    **kwargs,
) -> dict:
    """Insert an artifact row for a run and return it as a dict."""
    if isinstance(run_id, dict):
        payload = dict(run_id)
        if db_path is None and _looks_like_db_path(kind):
            db_path = kind
        run_id = payload.get("run_id", "")
        kind = payload.get("kind", "")
        path = payload.get("path", "")
    if db_path is None and "db_path" in kwargs:
        db_path = kwargs.pop("db_path")
    created_at = _now_iso()
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO artifacts (run_id, kind, path, created_at)"
            " VALUES (?, ?, ?, ?)",
            (run_id, kind, path, created_at),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, run_id, kind, path, created_at"
            " FROM artifacts WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return dict(row)


def list_artifacts(run_id: str | Path | None = None, db_path=None, **kwargs) -> list[dict]:
    """List artifact rows as dicts; None run_id lists every artifact."""
    if db_path is None and "db_path" in kwargs:
        db_path = kwargs["db_path"]
    if run_id is not None and _looks_like_db_path(run_id) and db_path is None:
        db_path, run_id = run_id, None
    with _connect(db_path) as conn:
        if run_id is None:
            rows = conn.execute(
                "SELECT id, run_id, kind, path, created_at"
                " FROM artifacts ORDER BY id"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, run_id, kind, path, created_at"
                " FROM artifacts WHERE run_id = ? ORDER BY id",
                (run_id,),
            ).fetchall()
    return [dict(row) for row in rows]


__all__ = [
    "DEFAULT_DB_PATH",
    "create_run",
    "get_run",
    "init_db",
    "insert_artifact",
    "insert_paper",
    "list_artifacts",
    "list_papers",
]
