"""GET /api/runs/{id}/events SSE trace (offline, never 500)."""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from db.models import get_run

router = APIRouter(prefix="/api/runs", tags=["runs-events"])


def _text_of(detail) -> str:
    try:
        return json.dumps(detail, sort_keys=True, default=str)[:2000]
    except Exception:
        try:
            return str(detail)[:2000]
        except Exception:
            return ""


def _agui_events_for(row: dict) -> list[dict]:
    """Replay persisted run state as finite AG-UI protocol events."""
    run_id = row.get("run_id", "")
    verdict = row.get("verdict")
    trace = row.get("trace")
    if not isinstance(trace, list):
        trace = []
    events: list[dict] = [{"type": "RUN_STARTED", "runId": run_id}]
    if not trace:
        events.append(
            {
                "type": "TEXT_MESSAGE_CONTENT",
                "role": "assistant",
                "delta": f"run {run_id} {row.get('status', 'queued')}",
            }
        )
        events.append(
            {
                "type": "TOOL_CALL_START",
                "toolCallId": f"{run_id}-run",
                "toolCallName": "run",
                "input": run_id,
            }
        )
        events.append(
            {
                "type": "TOOL_CALL_RESULT",
                "toolCallId": f"{run_id}-run",
                "result": str(row.get("status", "queued")),
            }
        )
    else:
        for entry in trace:
            if not isinstance(entry, dict):
                continue
            stage = entry.get("stage", "step")
            detail = entry.get("detail", {})
            text = _text_of(detail)
            events.append(
                {
                    "type": "TEXT_MESSAGE_CONTENT",
                    "role": "assistant",
                    "delta": f"{stage}: {text}",
                }
            )
            events.append(
                {
                    "type": "TOOL_CALL_START",
                    "toolCallId": f"{run_id}-{stage}",
                    "toolCallName": str(stage),
                    "input": text[:1000],
                }
            )
            events.append(
                {
                    "type": "TOOL_CALL_RESULT",
                    "toolCallId": f"{run_id}-{stage}",
                    "result": text,
                }
            )
    events.append({"type": "RUN_FINISHED", "runId": run_id, "verdict": verdict})
    return events


def _sse_body(events: list[dict]) -> str:
    return "".join(f"data: {json.dumps(event)}\n\n" for event in events)


@router.get("/{run_id}/events")
def get_run_events(run_id: str):
    row = get_run(run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="unknown run")
    body = _sse_body(_agui_events_for(row))
    return StreamingResponse(
        iter([body]),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
