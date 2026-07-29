"""A tiny in-process job manager for long-running work (loading cells).

Single-user desktop means we don't need Celery/Redis. Jobs run on a small
thread pool, report progress through a callback, can be cancelled cooperatively,
and stream their events to the browser over Server-Sent Events.
"""

from __future__ import annotations

import queue
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable


class Cancelled(Exception):
    """Raised inside a job when cancellation has been requested."""


@dataclass
class Progress:
    """Handle passed into job functions to report progress and check cancel."""

    _job: "Job"

    def update(self, fraction: float | None = None, message: str | None = None) -> None:
        if self._job.cancel_event.is_set():
            raise Cancelled()
        if fraction is not None:
            self._job.progress = max(0.0, min(1.0, fraction))
        if message is not None:
            self._job.message = message
        self._job._emit()

    def check_cancel(self) -> None:
        if self._job.cancel_event.is_set():
            raise Cancelled()


@dataclass
class Job:
    id: str
    kind: str
    status: str = "pending"  # pending|running|done|error|cancelled
    progress: float = 0.0
    message: str = ""
    result: Any = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    cancel_event: threading.Event = field(default_factory=threading.Event)
    _subscribers: list["queue.Queue[dict]"] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def snapshot(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "status": self.status,
            "progress": round(self.progress, 4),
            "message": self.message,
            "error": self.error,
        }

    def subscribe(self) -> "queue.Queue[dict]":
        q: queue.Queue[dict] = queue.Queue()
        with self._lock:
            self._subscribers.append(q)
        q.put(self.snapshot())  # send current state immediately
        return q

    def unsubscribe(self, q: "queue.Queue[dict]") -> None:
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def _emit(self) -> None:
        snap = self.snapshot()
        with self._lock:
            for q in list(self._subscribers):
                q.put(snap)


class JobManager:
    def __init__(self, max_workers: int = 2) -> None:
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="csg-job")
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def submit(self, kind: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], kind=kind)
        with self._lock:
            self._jobs[job.id] = job
        self._pool.submit(self._run, job, fn, args, kwargs)
        return job

    def _run(self, job: Job, fn: Callable[..., Any], args: tuple, kwargs: dict) -> None:
        job.status = "running"
        job.message = "Starting…"
        job._emit()
        progress = Progress(job)
        try:
            job.result = fn(progress, *args, **kwargs)
            if job.cancel_event.is_set():
                job.status = "cancelled"
                job.message = "Cancelled"
            else:
                job.status = "done"
                job.progress = 1.0
                job.message = "Done"
        except Cancelled:
            job.status = "cancelled"
            job.message = "Cancelled"
        except Exception as exc:  # noqa: BLE001
            job.status = "error"
            job.error = str(exc)
            job.message = f"Error: {exc}"
            traceback.print_exc()
        finally:
            job._emit()

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job and job.status in ("pending", "running"):
            job.cancel_event.set()
            return True
        return False


_MANAGER: JobManager | None = None


def get_job_manager() -> JobManager:
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = JobManager()
    return _MANAGER
