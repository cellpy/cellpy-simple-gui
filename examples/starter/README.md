# cellpy starter app

One file. Load battery cells, plot them, download the numbers.

```bash
uv run examples/starter/app.py
```

Then open <http://127.0.0.1:8000> and press **Load demo cell**.

[`app.py`](app.py) carries its own dependencies in a PEP 723 header, so it also
runs on its own, outside this repository:

```bash
uv run --script app.py
```

Copy it somewhere, rename it, start deleting things you do not need. That is
what it is for.

## What this is

The shortest honest path from "I have cell files" to "I have a chart and a CSV".

cellpy-simple-gui — the app in the rest of this repository — is a reference
implementation, and at ~8,000 lines it is a bad thing to start from. This is the
starting point: ~340 lines, of which about a quarter is the web page. Small
enough to read in one sitting, and small enough to keep in front of you (or in a
coding agent's context) while you work on something else.

**Not in it, on purpose:** saved projects, background jobs, browser upload,
authentication, themes, dev mode, instrument metadata forms. Every one of those
is a real feature with a real cost, and you should add them when you need them.

## The four calls

The whole cellpy story, and the four sections of `app.py`:

| Call | In | Out |
|---|---|---|
| `cellpy.get(filename=…)` | one file | one `CellpyCell` |
| `from_cells({name: cell})` | cells you already hold | a `Batch` |
| `collect_summaries(batch, columns=…)` | a `Batch` | a `Collection` |
| `collection.plot()` | a `Collection` | a plotly `Figure` |

The load-bearing one is **`from_cells`**. It takes cells that are already in
memory and hands back a real cellpy `Batch`, which means grouping, group
averaging, spread bands, cycle selection and multi-format export are cellpy's
job rather than yours. Assembling frames by hand instead is the most common way
to end up maintaining a worse copy of cellpy.

A `Collection` is a tidy [polars](https://pola.rs) frame (`.data`) that knows
how to draw itself (`.plot()`). Both the chart and the CSV in `app.py` come from
the same `Collection`, so the download always matches what is on screen.

## Adding a plot

`SUMMARY_PLOTS` maps a menu entry to the `cell.data.summary` columns behind it.
Adding a plot is adding a line — nothing else in the file knows the names:

```python
SUMMARY_PLOTS: dict[str, tuple[str, ...]] = {
    ...
    "C-rate": ("charge_c_rate", "discharge_c_rate"),
}
```

Reload the page. The menu, the chart, the CSV and the axis labels all follow.

To find out what you can put there, ask a cell you have loaded:

```python
list(cell.data.summary.columns)   # 53 of them on the bundled demo cell
```

Two things about those names that cost time if you learn them the hard way:

- **The suffix is the capacity basis.** `discharge_capacity_gravimetric` is per
  gram, `_areal` is per cm², and no suffix is absolute. They are different
  columns, not a display setting, and the gravimetric ones are only meaningful
  if the cell knows its active mass (`cellpy.get(..., mass=…)`).
- **A column the data does not have draws an empty chart rather than raising.**
  `app.py` checks first and says which ones are missing; if you drop that check,
  put something else in its place.

Plots that are not a column selection — voltage curves, dQ/dV, dV/dQ — are a
different *collector*, not a different column list. `collect_cycles` is in
`app.py`; `collect_ica` and `collect_dva` are its siblings and take the same
shape of options.

## What to add next, and where to look

When you outgrow this, the reference implementation has each piece in one place:

| You want | Look at |
|---|---|
| cellpy's own plot families, not a hand-written column table | `src/cellpy_simple_gui/core/collect.py` (`registry_plot_types`, `family_summary_options`) |
| dQ/dV and dV/dQ | `core/collect.py` (`ica_collection`, `dva_collection`) |
| Saving and reopening a set of cells | `core/projects.py` |
| Long loads that must not block the page | `api/jobs.py` |
| Serving it to a browser that is not on this machine | `core/paths.py`, `core/uploads.py`, and [`docs/deployment.md`](../../docs/deployment.md) |
| Static PNG/SVG/PDF export | `core/export.py` |

## Honest limitations

- **Localhost only, no authentication.** `POST /api/cells` takes a path and
  reads it, so anything that can reach the port can read any file the process
  can. That is fine on your own machine and nowhere else. Serving it for real
  means closing that surface first — see `core/paths.py` and
  [`docs/deployment.md`](../../docs/deployment.md), which exist because this app
  had to solve it.
- **One user, one process.** Loaded cells are a module-level dict, and cellpy's
  configuration is process-global besides. Two browsers on one process share
  both. This is a deliberate simplification, not an oversight — but it is the
  first thing to fix if more than one person will use it at once.
- **plotly.js comes from a CDN,** so the page needs network on first load. The
  full app vendors it instead.
- **The demo cell downloads once** from cellpy's example-data repository and is
  then cached under `~/cellpy_data`.
