"""A tiny in-process job manager for long-running work (loading cells).

Single-user desktop means we don't need Celery/Redis. Jobs run on a small
thread pool, report progress through a callback, can be cancelled cooperatively,
and stream their events to the browser over Server-Sent Events.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable

log = logging.getLogger(__name__)


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


class _DaemonThreadPoolExecutor(ThreadPoolExecutor):
    """Like ThreadPoolExecutor, but workers are daemons so app exit is not blocked.

    A stuck cellpy load must not pin the console after the window closes.
    """

    def _adjust_thread_count(self) -> None:
        # Mirror stdlib logic with daemon=True (stdlib workers are non-daemon).
        import weakref

        from concurrent.futures.thread import _threads_queues, _worker

        if self._idle_semaphore.acquire(timeout=0):
            return

        def weakref_cb(_, q=self._work_queue):
            q.put(None)

        num_threads = len(self._threads)
        if num_threads < self._max_workers:
            thread_name = "%s_%d" % (self._thread_name_prefix or self, num_threads)
            t = threading.Thread(
                name=thread_name,
                target=_worker,
                args=(
                    weakref.ref(self, weakref_cb),
                    self._work_queue,
                    self._initializer,
                    self._initargs,
                ),
                daemon=True,
            )
            t.start()
            self._threads.add(t)
            _threads_queues[t] = self._work_queue


class JobManager:
    def __init__(self, max_workers: int = 2) -> None:
        self._pool = _DaemonThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="csg-job"
        )
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._closed = False

    def submit(self, kind: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Job:
        if self._closed:
            raise RuntimeError("Job manager has been shut down.")
        job = Job(id=uuid.uuid4().hex[:12], kind=kind)
        with self._lock:
            self._jobs[job.id] = job
        log.info("Job %s started (%s)", job.id, kind)
        self._pool.submit(self._run, job, fn, args, kwargs)
        return job

    def shutdown(self) -> None:
        """Cancel running jobs and stop the pool without waiting on stuck work."""
        if self._closed:
            return
        self._closed = True
        with self._lock:
            running = [
                j for j in self._jobs.values() if j.status in ("pending", "running")
            ]
        for job in running:
            job.cancel_event.set()
        log.info("Shutting down job manager (%d job(s) signalled)", len(running))
        try:
            self._pool.shutdown(wait=False, cancel_futures=True)
        except TypeError:  # pragma: no cover - older Python
            self._pool.shutdown(wait=False)

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
                log.info("Job %s cancelled (%s)", job.id, job.kind)
            else:
                job.status = "done"
                job.progress = 1.0
                job.message = "Done"
                summary = _job_result_summary(job.result)
                if summary:
                    log.info("Job %s done (%s): %s", job.id, job.kind, summary)
                else:
                    log.info("Job %s done (%s)", job.id, job.kind)
                for err in _job_result_errors(job.result):
                    log.error("Job %s (%s): %s", job.id, job.kind, err)
        except Cancelled:
            job.status = "cancelled"
            job.message = "Cancelled"
            log.info("Job %s cancelled (%s)", job.id, job.kind)
        except Exception as exc:  # noqa: BLE001
            job.status = "error"
            job.error = str(exc)
            job.message = f"Error: {exc}"
            log.exception("Job %s failed (%s): %s", job.id, job.kind, exc)
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


def _job_result_summary(result: Any) -> str:
    """One-line summary of common job result dicts (load / ingest / project)."""
    if not isinstance(result, dict):
        return ""
    parts: list[str] = []
    if "added" in result:
        parts.append(f"{len(result['added'])} cell(s) added")
    errors = result.get("errors") or []
    if errors:
        parts.append(f"{len(errors)} error(s)")
    if result.get("action") and result.get("name"):
        parts.append(
            f"{result['action']} “{result['name']}” ({result.get('n_cells', '?')} cells)"
        )
    notes = result.get("notes") or []
    if notes:
        parts.append("; ".join(str(n) for n in notes[:2]))
    return "; ".join(parts)


def _job_result_errors(result: Any) -> list[str]:
    if not isinstance(result, dict):
        return []
    errors = result.get("errors") or []
    return [str(e) for e in errors[:10]]


def get_job_manager() -> JobManager:
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = JobManager()
    return _MANAGER
