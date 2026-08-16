"""The job pool, and the stdlib coupling that used to break it (#123).

The pool used to be a ``ThreadPoolExecutor`` subclass that re-implemented the
private ``_adjust_thread_count`` in order to get daemon workers. That copied
CPython internals, and CPython moved: 3.14 replaced
``_worker(ref, queue, initializer, initargs)`` with ``_worker(ref, ctx, queue)``
and dropped ``_initializer`` entirely, so *every job* raised

    AttributeError: '_DaemonThreadPoolExecutor' object has no attribute '_initializer'

on any interpreter newer than the one it was written against. Nothing in the
suite noticed, because the suite only ever ran on 3.13. It surfaced from
``uv tool install``, which picked 3.14 — i.e. from the install route real users
would take.

These tests pin the behaviour the pool has to provide, without depending on any
private stdlib detail.
"""

from __future__ import annotations

import threading
import time

import pytest

from cellpy_simple_gui.api import jobs

pytestmark = pytest.mark.essential


def test_jobs_do_not_depend_on_private_stdlib_internals():
    """The regression guard: no reaching into concurrent.futures internals.

    A test that merely runs a job would have passed on 3.13 while the app was
    broken on 3.14, so this asserts on the *coupling* rather than the outcome.

    Parsed rather than grepped: the module's own docstring explains this
    history and names every forbidden symbol, so a text search matches the
    prose describing the bug instead of the code causing it.
    """
    import ast
    from pathlib import Path

    tree = ast.parse(Path(jobs.__file__).read_text(encoding="utf-8"))

    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    offending = {m for m in imported if m.startswith("concurrent.futures")}
    assert not offending, (
        f"imports CPython-internal machinery {sorted(offending)}; "
        "_worker's signature changed in 3.14 and took every job with it"
    )

    attributes = {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    for private in ("_initializer", "_initargs", "_idle_semaphore"):
        assert private not in attributes, f"{private} is a stdlib private attribute"


def test_pool_workers_are_daemons():
    """A stuck cellpy load must not pin the process after the window closes."""
    pool = jobs._DaemonPool(max_workers=2, name_prefix="test-pool")
    try:
        assert len(pool._threads) == 2
        assert all(t.daemon for t in pool._threads)
    finally:
        pool.shutdown()


def test_pool_runs_submitted_work():
    pool = jobs._DaemonPool(max_workers=2, name_prefix="test-pool")
    done = threading.Event()
    seen: list[tuple] = []

    try:
        pool.submit(lambda *a: (seen.append(a), done.set()), 1, "two")
        assert done.wait(timeout=5), "work was never executed"
        assert seen == [(1, "two")]
    finally:
        pool.shutdown()


def test_one_failing_job_does_not_kill_the_worker():
    """Otherwise the first bad job silently costs a worker for the session."""
    pool = jobs._DaemonPool(max_workers=1, name_prefix="test-pool")
    survived = threading.Event()

    def boom():
        raise RuntimeError("job blew up")

    try:
        pool.submit(boom)
        pool.submit(survived.set)
        assert survived.wait(timeout=5), "the worker died with the failing job"
    finally:
        pool.shutdown()


def test_manager_runs_a_job_end_to_end():
    manager = jobs.JobManager(max_workers=1)
    try:
        job = manager.submit("test", lambda progress: {"added": ["c1"]})
        deadline = time.time() + 10
        while time.time() < deadline and job.status in ("pending", "running"):
            time.sleep(0.02)
        assert job.status == "done", job.error
        assert job.result == {"added": ["c1"]}
        assert job.elapsed_seconds is not None
    finally:
        manager.shutdown()


def test_manager_reports_a_failing_job_rather_than_hanging():
    manager = jobs.JobManager(max_workers=1)

    def boom(progress):
        raise ValueError("no such cell")

    try:
        job = manager.submit("test", boom)
        deadline = time.time() + 10
        while time.time() < deadline and job.status in ("pending", "running"):
            time.sleep(0.02)
        assert job.status == "error"
        assert "no such cell" in (job.error or "")
    finally:
        manager.shutdown()


def test_shutdown_does_not_wait_on_a_stuck_job():
    """shutdown() signals cancellation and returns; it must never join."""
    manager = jobs.JobManager(max_workers=1)
    started = threading.Event()
    release = threading.Event()

    def stuck(progress):
        started.set()
        release.wait(timeout=30)  # deliberately outlives the shutdown

    manager.submit("test", stuck)
    assert started.wait(timeout=5)

    began = time.time()
    manager.shutdown()
    assert time.time() - began < 2.0, "shutdown blocked on a running job"
    release.set()
