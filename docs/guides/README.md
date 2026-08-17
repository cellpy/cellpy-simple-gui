# Building on cellpy

Seven guides, organised by what you are trying to do rather than by module. The
module layout is discoverable from the source; the task mapping is not.

They are written against **cellpy 2.1.2** from building
[cellpy-simple-gui](../../README.md) on it — 29 issues filed upstream, 25 closed.
Where a guide names a trap, it is one we walked into, and the evidence is the
measurement rather than an opinion.

| | Guide | You are trying to |
|---|---|---|
| 1 | [Getting cells into memory](01-loading-cells.md) | open a file, a folder, or a journal, and find out why one will not open |
| 2 | [Cells into a Collection](02-collections.md) | get many cells into one frame you can plot and export |
| 3 | [Plotting a collection](03-plotting.md) | draw it, and build a plot menu that is not a hard-coded list |
| 4 | [Exporting data and figures](04-exporting.md) | get numbers and images out, in memory, without temp files |
| 5 | [Configuration](05-configuration.md) | find out where cellpy is reading from, and change it safely |
| 6 | [Process state and threading](06-state-and-threading.md) | call cellpy from a worker thread without cross-talk |
| 7 | [What cellpy will and will not do for you](07-delegation.md) | decide whether to write the code or let cellpy do it |

New to this? [`examples/starter/`](../../examples/starter/) is a running app in
one file that does 1 → 4. Read it first; these guides are what is behind it.

## Every Python block here runs

Blocks fenced as ` ```python ` are executed, in document order, by
[`tests/test_guides.py`](../../tests/test_guides.py). A guide whose code stops
working against a new cellpy breaks CI rather than the reader.

Blocks fenced as ` ```pycon ` are REPL transcripts — usually illustrating
something going *wrong*, which is why they are not run.

That means you can copy a guide from the top and it will work, and it means the
outputs quoted here were real when written. It also means the guides are
deliberately narrow: everything shown had to be demonstrable on the bundled
example cells.

## Two things worth knowing before you start

**Hand cellpy your cells, do not hand yourself cellpy's job.**
`cellpy.collect.from_cells` turns cells you already hold into a real `Batch`, and
from there grouping, group averaging, spread bands, per-cell cycle isolation and
multi-format export are cellpy's problem. The single most expensive mistake
available here is assembling frames by hand and slowly reimplementing a worse
copy of `cellpy.collect`.

**The frames are [polars](https://pola.rs), the cells are pandas.**
`collection.data` is a polars DataFrame; `cell.data.summary` and `cell.data.raw`
are pandas. Crossing that boundary is explicit (`.to_pandas()`), and forgetting
which side you are on is the most common five-minute confusion in this codebase.

## If something here is wrong

These guides describe a moving library. [`CELLPY_PAINPOINTS.md`](../../CELLPY_PAINPOINTS.md)
records every rough edge found while building on it and which upstream issue
closed it, so if a workaround here looks unnecessary, check there first — it may
already have been fixed and not yet deleted.
