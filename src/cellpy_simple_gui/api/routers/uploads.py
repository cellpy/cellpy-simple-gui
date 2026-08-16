"""Bringing files in through the browser (#133).

Upload writes into ``CSG_DATA_DIR/uploads`` and hands back the resulting paths;
loading them is then the existing ``/load/files`` or ``/ingest``, which already
know how to read anything inside the data directory. Keeping upload and load
separate means the sandbox (#120) stays the single place that decides what is
readable, instead of gaining a second door.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, HTTPException, UploadFile

from ...core import uploads

log = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload")
async def upload(files: list[UploadFile] = File(...)) -> dict:
    """Accept one or more files; report what landed and what did not.

    A rejected file does not fail the request. Uploading five and having one
    exceed the cap should leave you with four and a clear message, not nothing
    and a 400 — the four are exactly as useful as they would have been.
    """
    if not files:
        raise HTTPException(400, "No files provided.")

    saved, errors = [], []
    for item in files:
        try:
            result = uploads.save(item.file, item.filename)
        except uploads.UploadRejected as exc:
            errors.append(str(exc))
        except OSError as exc:
            log.error("Upload failed (%s): %s", item.filename, exc)
            errors.append(f"{item.filename}: could not be written ({exc}).")
        else:
            saved.append({"path": str(result.path), "name": result.path.name,
                          "bytes": result.size})
        finally:
            await item.close()

    if not saved and errors:
        raise HTTPException(400, "; ".join(errors))

    log.info("Upload: %d saved, %d rejected", len(saved), len(errors))
    return {"saved": saved, "errors": errors, "usage": uploads.usage()}


@router.get("/uploads")
def list_uploads() -> dict:
    return {"usage": uploads.usage(), "max_upload_mb": uploads.max_upload_bytes() >> 20}


@router.delete("/uploads")
def clear_uploads() -> dict:
    """Delete every uploaded file. Never happens on a timer — see core.uploads."""
    return uploads.clear()
