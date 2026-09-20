"""Remote folder discovery over SSH/SFTP (cellpy filefinder, #162).

Phase 1 (#160) lets a desktop user paste one ``sftp://…/file`` URI. This is the
"approximate glob" for it: walk a remote *folder* and hand back concrete file
URIs the existing load / ingest jobs accept. Runs as a job because an SFTP walk
of a shared raw-data folder can take minutes and cellpy offers no progress hook.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from ...core import cellpy_adapter
from ...core.models import RemoteFindRequest
from ..jobs import Progress, get_job_manager

log = logging.getLogger(__name__)
router = APIRouter()


def _remote_find_job(progress: Progress, req: RemoteFindRequest) -> dict:
    from ...core.files import effective_max_files

    progress.update(
        0.05,
        f"Searching {req.directory} … (SFTP walks can take a while; cancel does "
        "not interrupt the remote listing)",
    )
    found = cellpy_adapter.find_remote_files(
        req.directory,
        extensions=req.extensions,
        filter_text=req.filter,
        max_files=effective_max_files(req.max_files),
    )
    progress.update(1.0)
    return {
        "paths": found.paths,
        "total": found.total,
        "errors": found.errors,
        "notes": found.notes,
    }


@router.post("/remote/find")
def remote_find(req: RemoteFindRequest) -> dict:
    if not req.directory.strip():
        raise HTTPException(400, "No remote folder provided")
    log.info(
        "Remote find: %s (%s, filter=%r)",
        req.directory,
        ", ".join(req.extensions) or "all files",
        req.filter,
    )
    job = get_job_manager().submit("remote-find", _remote_find_job, req)
    return {"job_id": job.id}
