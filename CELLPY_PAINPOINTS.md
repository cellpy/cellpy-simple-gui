# cellpy pain-points & wishlist (from building cellpy-simple-gui)

Notes gathered while building a small desktop GUI on **cellpy 2.1.0.post1**. The
goal here is constructive: these are the places where the library made an app
harder to build than it needed to be, each with a concrete suggestion. Ordered
roughly by impact.

Legend: 🔴 blocker / had to work around · 🟠 friction · 🟢 nice-to-have.

---

## 1. 🔴 No public "collection from in-memory cells"

`collect_summaries` / `collect_cycles` are exactly the right tools, but they only
accept a `batch` object that exposes `.cells` (`{label: CellpyCell}`) **and**
`.journal.pages` (a **polars** frame with `filename` / `group` / `sub_group` /
`group_label` / `label` / `selected`). There is no public way to get such an
object from a set of already-loaded `CellpyCell`s.

I had to reverse-engineer the contract and duck-type a shim
(`core/collect.py::_BatchShim`). It also turned out `collect_summaries` reads
`batch.journal.name` — an undocumented required attribute that only surfaced as
an `AttributeError` at runtime.

**Wish:** a supported constructor, e.g.

```python
collection = cellpy.collect.from_cells(
    cells,                       # list/dict of CellpyCell
    groups={label: 1, ...},      # optional
    selected={label: True, ...}, # optional
)
```

or `Batch.from_cells(...)`. This is the single biggest enabler for GUIs/notebooks
that manage cells in memory rather than from a journal on disk.

## 2. 🔴 Group-averaged summaries can be collected but not plotted

```python
col = collect_summaries(batch, columns=("charge_capacity_gravimetric",), group_it=True)
col.plot()            # KeyError: 'cell'
col.plot(spread=True) # KeyError: 'mean'  (when 1 cell/group) or 'cell'
```

Traceback bottoms out in `cellpy/plotting/collected.py::spread_plot`, which does
`curves.groupby("cell")` — but a group-averaged frame is keyed by `group`
(columns `group, cycle_num, variable, mean, std`), so there is no `cell` column.
The **data** side (averaging) works; only the **plot** side breaks. I ended up
degrading gracefully (`figure_json` falls back to a plain render / empty figure)
and exposing group-averaging as a data/export feature only.

**Wish:** make the collected summary renderer accept group-averaged frames
(`groupby("group")` when there is no `cell` column), so `group_it=True` is
plottable end-to-end.

## 3. 🟠 Silent group-averaging fallback with no signal on the result

`group_it=True` silently returns a *wide, non-averaged* frame when any group has
< 2 cells (the "std needs ≥ 2 cells" guard in `collect/summary.py`). Sensible,
but the returned `Collection` carries no flag saying whether averaging actually
happened, so I sniff for a `mean` column (`collect.is_grouped`).

**Wish:** `Collection.meta.grouped: bool` (or `collection.is_grouped`) so callers
can adapt UI/labels without inspecting columns.

## 4. 🟠 `CurveOptions` can't set capacity mode / method

`CellpyCell.get_cap()` takes `mode` (`gravimetric`/`areal`/`absolute`) and
`method` (`forth-and-forth`/…), but `collect_cycles` / `CurveOptions` expose only
`cycles` / `rate`. So a multi-cell cycle-curve collection can't offer the
areal/absolute toggle a single cell can. I had to drop that control from the cell
explorer when moving to `collect_cycles`.

**Wish:** add `mode` / `method` to `CurveOptions` (and pass through to `get_cap`).

## 5. 🟠 Instrument discovery logs a WARNING per non-loader module

`instrument_configurations()` is the right API for "what can cellpy load" — but
it emits a `logging.warning(...)` for every non-loader module it skips
(`config_declarations`, `contract`, `hooks`, `declarations`, `registry`,
`testing`, and `custom` which "needs a definition file") **on every call**. An
app calling it at startup has to bracket it with a log-level bump
(`core/cellpy_adapter.py::list_instruments`).

**Wish:** a quiet, app-facing `list_instruments()` returning
`[{id, label, models, suffixes}]` with human labels and raw extensions. I keep my
own label/extension map today because the ids (`maccor_txt`, `pec_csv`) aren't
display-ready and the raw suffix isn't exposed alongside the models.

## 6. 🟠 `Collection.save()` only supports parquet/csv

`Collection.save(dir, formats=...)` raises `ValueError("unsupported collection
format")` for anything but `parquet`/`csv`, even though "save in different formats
for free" is a selling point of the collection design. I export `xlsx`/`json`
myself via `data.to_pandas().to_excel(...)` / `data.write_json()`.

**Wish:** support `xlsx` and `json` in `SaveOptions.formats` / `Collection.save`.

## 7. 🟠 polars vs pandas boundary is easy to trip on

`Collection.data` is **polars**; `cell.data.summary` is **pandas**;
`Collection.plot` internally does `.to_pandas()`. Apps end up juggling both and
guessing which a given function wants. `collect_summaries` also returns different
shapes (wide vs long) depending on `group_it`, which the plot layer then has to
reconcile (it renames `cycle_num`→`cycle` for the summary family).

**Wish:** document the dataframe boundary explicitly, and/or offer
`Collection.to_pandas()` plus a stable column contract per `kind`.

## 8. 🟠 `get_summary()` deprecation warning is noisy

`CellpyCell.get_summary()` is deprecated in favour of `cell.data.summary` (good),
but the `DeprecationWarning` fires readily and apps must blanket-suppress warnings
to keep logs/console clean. A one-line "how to silence cellpy warnings in an app"
in the docs would help.

## 9. 🟢 No lightweight metadata read

Listing many `.cellpy` files (e.g. a project browser) means a full
`cellpy.get(...)` per file just to show mass / area / #cycles. A cheap
`read_meta(path)` that reads header metadata without materialising raw/steps
would make file browsers snappy.

## 10. 🟢 No per-instrument metadata schema

When importing raw files, an app has to guess which metadata an instrument needs
(mass? area? nominal capacity? default units?). A declared schema per instrument
would let apps generate the right ingestion form automatically instead of showing
every field for every instrument.

## 11. 🟢 Collected figures aren't app-friendly by default

`collected_plot` returns faceted figures with default plotly styling: mirror axis
boxes, right-side facet titles spelled `variable=charge_capacity_gravimetric`, and
an auto height that grows with facet count. I re-style every figure
(`core/collect.py::_restyle`) to fit the app shell.

**Wish:** a theme/label/height hook (or a `FigureSpec` the caller can pass) so the
returned figure drops cleanly into an app without post-processing.

---

## What already works well (thank-you notes)

- `cellpy.get(...)` as a single entry point, with unit-string args
  (`mass="1.14 mg"`) — lovely.
- `collect_summaries` / `collect_cycles` fixing the cross-cell cycle-narrowing bug
  by per-cell isolation (`collect/cells.py`) — exactly the kind of correctness win
  an app can't easily do itself.
- `cellpy.utils.example_data` — made a zero-setup demo trivial.
- Arbin `.res` loading working on Windows via the Access ODBC driver with no
  mdbtools — pleasant surprise.
- The curated plot `families` registry — a great vocabulary for a plot-type menu.
- `instrument_configurations()` exists at all — discovery was possible; it just
  needs a quieter, app-facing wrapper (see #5).

*Generated while building [cellpy-simple-gui](./README.md) on cellpy 2.1.0.post1.*
