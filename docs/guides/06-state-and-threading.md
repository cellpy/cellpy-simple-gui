# 6. Process state and threading

*You want to load a 200 MB file without freezing the UI, and you want to know
what that costs you.*

Loading a cell takes seconds. Collecting across twenty of them takes longer. In
anything with a user interface that has to happen off the main thread, which
makes the question on this page unavoidable: **what in cellpy is per-call, and
what is per-process?**

## The short answer

| Thing | Scope | Safe from a worker thread? |
|---|---|---|
| `cellpy.get(...)` | per call | yes — everything it needs is an argument |
| `collect_*` / `Collection.plot` | per call | yes |
| `config.override(...)` | per thread / per asyncio task | yes — that is what it is for |
| `config.reload(...)` | **process** | only if a process-wide change is what you mean |
| `config.set_load_options(...)` | **process** | same |
| `example_data.DATA_PATH` | **process**, fixed at import | see [guide 5](05-configuration.md) |

The good news is that the data path — load, collect, plot — takes its inputs as
arguments and returns new objects. It is the *settings* that are shared.

## `override` is per thread; `reload` is not

Since 2.1.2a3 `config.override()` is built on `contextvars`, so two workers can
hold different values at the same time and nested blocks stack LIFO:

```python
import threading
import warnings

from cellpy import config

warnings.simplefilter("ignore")

seen = {}
both_inside = threading.Barrier(2)


def worker(name, mode):
    with config.override(reader={"cycle_mode": mode}):
        both_inside.wait()          # force the overlap; without it, no race to see
        seen[name] = config.get_config().reader.cycle_mode


threads = [threading.Thread(target=worker, args=a) for a in (("a", "anode"), ("b", "cathode"))]
for t in threads:
    t.start()
for t in threads:
    t.join()

print(dict(sorted(seen.items())))   # sorted: the threads finish in either order
```

```text
{'a': 'anode', 'b': 'cathode'}
```

The barrier is the load-bearing part of that test. Without it the two blocks
might never overlap, and a broken implementation would pass — which is exactly
how this was verified when
[cellpy#850](https://github.com/jepegit/cellpy/issues/850) was fixed. Before that
fix `override` was process-global, so a worker could change another worker's
units mid-job and the result was wrong rather than crashed.

`reload()` and `set_load_options()` are still process-global, deliberately.
Reach for them when you mean "this process now works this way" — switching to a
project's configuration, say — and for nothing finer-grained.

That distinction is a design decision you have to make too. In this app a
*project* switch calls `reload()` on the request thread rather than
`override()` per job, because a project switch really is process-wide: the user
changed what the application is working on, not what one job is doing.

## Your own singletons are the real constraint

cellpy's process-global surface is small. An app's is usually larger, and it is
worth being deliberate about rather than discovering later.

This one holds four: the in-memory cell library, the job manager, the active
project configuration, and an instrument-discovery cache. Together they mean
**two browsers pointed at one process share one library, one job queue and one
cellpy configuration**.

That is not a bug here — the app is deployed one instance per user, and the
whole design leans on it. But it is load-bearing, so it is written down: anything
that later wants to serve several people from one process starts by fixing those
four, plus cellpy's process-global config underneath them.

If you are building something multi-tenant, decide this on day one. Retrofitting
a request-scoped library into code that assumes a module-level dict is a rewrite,
not a refactor.

## A worker pool that survives its workers

Two things learned the hard way, both about `concurrent.futures`.

**Do not subclass `ThreadPoolExecutor` to change how workers start.** A daemon
pool built by copying CPython's private `_worker` and `_initializer` broke on
Python 3.14, when those internals changed shape:

```pycon
AttributeError: '_DaemonThreadPoolExecutor' object has no attribute '_initializer'
```

The failure is not the copy going stale — that was foreseeable — it is that it
only appears on a Python version nobody had tested yet. If you need behaviour the
standard pool does not offer, write the twenty lines: a queue, some daemon
threads, and a sentinel to stop them.

```python
import queue
import threading

_STOP = object()


class DaemonPool:
    """Threads that never block interpreter exit, and survive a failing job."""

    def __init__(self, workers: int = 2):
        self._queue: queue.Queue = queue.Queue()
        self._threads = [
            threading.Thread(target=self._run, daemon=True) for _ in range(workers)
        ]
        for t in self._threads:
            t.start()

    def _run(self):
        while True:
            item = self._queue.get()
            if item is _STOP:
                return
            fn, args = item
            try:
                fn(*args)
            except Exception:  # noqa: BLE001 - one bad job must not kill the worker
                pass

    def submit(self, fn, *args):
        self._queue.put((fn, args))

    def shutdown(self):
        for _ in self._threads:
            self._queue.put(_STOP)
        # Deliberately no join(): shutdown must not be able to hang exit.


pool = DaemonPool()
done = threading.Event()
pool.submit(lambda: (_ for _ in ()).throw(RuntimeError("boom")))  # a failing job
pool.submit(done.set)                                             # still runs
print("survived a failing job:", done.wait(timeout=5))
pool.shutdown()
```

```text
survived a failing job: True
```

Three properties worth stating, because each was a bug at some point: workers are
**daemon** threads so a hung job cannot stop the app exiting; a worker **survives
a failing job** rather than dying quietly and shrinking the pool to nothing; and
`shutdown` **never joins**, so shutdown cannot be the thing that hangs.

**Run CI on the newest Python, not only the supported one.** The 3.14 breakage
above existed for a while under a fully green build. A separate job pinned to the
newest release is cheap and is the only thing that would have caught it.

## Progress and cancellation

cellpy's calls are synchronous and do not take a progress callback, so anything
the user sees is granularity you impose from outside — per file, per cell, per
collect step. That is usually enough: "loading 3 of 12" is more useful than a
smooth bar over one opaque call.

Cancellation is the same story. There is no way to interrupt `cellpy.get` in
flight, so a cancel flag can only be honoured *between* units of work. Say so in
the UI — a Cancel button that takes effect after the current file is honest; one
that appears to stop instantly and does not is worse than no button.

## Where to go next

[Guide 7](07-delegation.md) — the running list of what cellpy will do for you, so
you can stop writing the parts it already owns.

---

*Sources: `cellpy.config.override` (contextvars),
`cellpy.config.reload` / `set_load_options`. Traps from
[CELLPY_PAINPOINTS.md](../../CELLPY_PAINPOINTS.md) §23 and
[cellpy-simple-gui#139](https://github.com/cellpy/cellpy-simple-gui/issues/139).*
