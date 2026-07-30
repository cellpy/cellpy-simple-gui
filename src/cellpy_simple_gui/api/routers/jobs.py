"""Job status, cancellation, and an SSE progress stream."""

from __future__ import annotations

import json
import queue

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..jobs import get_job_manager

router = APIRouter()


@router.get("/jobs/{job_id}")
def job_status(job_id: str) -> dict:
    job = get_job_manager().get(job_id)
    if job is None:
        raise HTTPException(404, "No such job")
    snap = job.snapshot()
    if job.status == "done":
        snap["result"] = job.result
    return snap


@router.post("/jobs/{job_id}/cancel")
def job_cancel(job_id: str) -> dict:
    job = get_job_manager().get(job_id)
    if job is None:
        raise HTTPException(404, "No such job")
    ok = get_job_manager().cancel(job_id)
    return {"cancelled": ok, "status": job.status}


@router.get("/jobs/{job_id}/events")
def job_events(job_id: str) -> StreamingResponse:
    job = get_job_manager().get(job_id)
    if job is None:
        raise HTTPException(404, "No such job")

    def event_stream():
        q = job.subscribe()
        try:
            while True:
                try:
                    snap = q.get(timeout=15)
                except queue.Empty:
                    yield ": keep-alive\n\n"  # heartbeat
                    continue
                if job.status == "done":
                    snap = {**snap, "result": job.result}
                yield f"data: {json.dumps(snap)}\n\n"
                if snap["status"] in ("done", "error", "cancelled"):
                    break
        finally:
            job.unsubscribe(q)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
