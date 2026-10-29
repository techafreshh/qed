"""POST /api/runs and GET /api/runs/{id}[/notebook] (offline, never 500)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from db.models import create_run, get_run
from library.schema import load_library

router = APIRouter(prefix="/api/runs", tags=["runs"])

# Acceptance paper ids that resolve even when the library is unreadable.
_DEMO_PAPER_IDS = frozenset({"demo_replicated", "demo_failed", "example_replication"})

# Manifest id of the placeholder fixture; not a real frozen paper.
_FIXTURE_MANIFEST_ID = "example_replication"


class RunIn(BaseModel):
    """POST /api/runs body; both fields required non-blank (else 422)."""

    paper_id: str = Field(min_length=1)
    claim: str = Field(min_length=1)

    @field_validator("paper_id", "claim")
    @classmethod
    def _non_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


def known_paper_ids() -> set[str]:
    """Frozen manifest ids plus demo ids; degrades to demo ids, never raises."""
    try:
        ids = {manifest.id for manifest in load_library()}
    except Exception:
        return set(_DEMO_PAPER_IDS)
    ids.discard(_FIXTURE_MANIFEST_ID)
    return ids | set(_DEMO_PAPER_IDS)


def _notebook_url(run_id: str) -> str:
    return f"/api/runs/{run_id}/notebook"


def _trace_for(row: dict) -> list[dict]:
    return [
        {
            "stage": row.get("status", "queued"),
            "ts": row.get("created_at", ""),
            "detail": f"run {row.get('run_id', '')} {row.get('status', 'queued')}"
            f" for paper {row.get('paper_id', '')}",
        }
    ]


def _run_detail(row: dict) -> dict:
    return {
        "run_id": row.get("run_id"),
        "paper_id": row.get("paper_id"),
        "status": row.get("status", "queued"),
        "verdict": row.get("verdict"),
        "fragile_choice": None,
        "trace": _trace_for(row),
        "notebook_url": _notebook_url(row.get("run_id", "")),
    }


def _notebook_for(row: dict) -> dict:
    return {
        "run_id": row.get("run_id"),
        "paper_id": row.get("paper_id"),
        "status": row.get("status", "queued"),
        "verdict": row.get("verdict"),
        "cells": [
            {
                "cell_type": "markdown",
                "source": f"# QED replication notebook for {row.get('run_id', '')}",
            },
            {
                "cell_type": "code",
                "source": f'paper_id = "{row.get("paper_id", "")}"',
                "outputs": [],
            },
        ],
    }


def _require_run(run_id: str) -> dict:
    row = get_run(run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="unknown run")
    return row


@router.post("", status_code=202, include_in_schema=False)
def create_run_no_slash(body: RunIn) -> dict:
    return _create_run(body)


@router.post("/", status_code=202)
def create_run_slash(body: RunIn) -> dict:
    return _create_run(body)


def _create_run(body: RunIn) -> dict:
    if body.paper_id not in known_paper_ids():
        raise HTTPException(status_code=404, detail="unknown paper")
    row = create_run(paper_id=body.paper_id)
    return {"run_id": row["run_id"], "status": row.get("status", "queued")}


@router.get("/{run_id}")
def get_run_detail(run_id: str) -> dict:
    return _run_detail(_require_run(run_id))


@router.get("/{run_id}/notebook")
def get_run_notebook(run_id: str) -> dict:
    row = _require_run(run_id)
    if row.get("status") != "complete":
        raise HTTPException(status_code=409, detail="run not yet complete")
    return _notebook_for(row)
