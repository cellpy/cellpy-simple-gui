# cellpy pain-points & wishlist (from building cellpy-simple-gui)

Notes gathered while building a small desktop GUI on **cellpy 2.1.0.post1**. The
goal here is constructive: these are the places where the library made an app
harder to build than it needed to be, each with a concrete suggestion. Ordered
roughly by impact.

Legend: 🔴 blocker / had to work around · 🟠 friction · 🟢 nice-to-have.

> **Update — most of these are fixed in cellpy 2.1.1+** 🎉 Filed upstream as
> [jepegit/cellpy#785–#791](https://github.com/jepegit/cellpy/issues/785) and
> follow-ups; the app runs on **≥2.1.1.post4** (see
> `.issueflows/04-designs-and-guides/cellpy-delegation-inventory.md`).
>
> | # | Item | Upstream | Status |
> |---|---|---|---|
> | 1 | Collection from in-memory cells | [#787](https://github.com/jepegit/cellpy/issues/787) | ✅ `cellpy.collect.from_cells` / `Batch.from_cells` |
> | 2 | Group-averaged summary can't plot | [#785](https://github.com/jepegit/cellpy/issues/785) | ✅ renders (bug fixed) |
> | 3 | No "was it averaged?" signal | [#790](https://github.com/jepegit/cellpy/issues/790) | ✅ `Collection.is_grouped` + `meta.grouped` (all-or-nothing avg still app-partitioned) |
> | 4 | `CurveOptions` mode/method | [#788](https://github.com/jepegit/cellpy/issues/788) | ✅ added |
> | 5 | Quiet, app-facing instrument list | [#786](https://github.com/jepegit/cellpy/issues/786) | ✅ quiet by contract in **2.1.1.post3** |
> | 6 | `Collection.save` xlsx/json | [#789](https://github.com/jepegit/cellpy/issues/789) | ✅ supported |
> | 9 | Lightweight `read_meta` | [#799](https://github.com/jepegit/cellpy/issues/799) | ✅ **2.1.1.post4** — app wraps as `cellpy_adapter.read_file_meta` |
> | 10 | Per-instrument metadata schema | [#800](https://github.com/jepegit/cellpy/issues/800) | ✅ **2.1.1.post4** — app wraps as `instrument_meta_schema` (UI follow-up) |
> | 11 | App-friendly collected figures | [#801](https://github.com/jepegit/cellpy/issues/801) | ✅ **2.1.1.post4** hooks; app still owns legend/colorway |
> | 12 | Per-panel y-limits / `share_y` | [#804](https://github.com/jepegit/cellpy/issues/804) | ✅ **2.1.1.post2** (spread path still needs app `#47` re-link) |
> | 7–8, 13–16 | polars docs, deprecation noise, figure bytes, `.h5` auto_pick, cycles/ICA plot gaps | — | ◑ still open / app workarounds |
>
> The notes below are kept as originally written (against 2.1.0) for context.

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

## 3. 🟠 Silent all-or-nothing group-averaging when any group is a singleton

`group_it=True` silently returns a *wide, non-averaged* frame when **any** group
has < 2 cells (the "std needs ≥ 2 cells" guard in `collect/summary.py`). One
singleton in the selection disables averaging for *every* group — including
those with plenty of members. GUIs that default each cell to its own group (or
mix multi-cell and single-cell groups) see "Group average" appear to do nothing.
The returned `Collection` also carries no flag saying whether averaging actually
happened, so callers sniff for a `mean` column (`collect.is_grouped`).

Workaround in this app (#27): partition selected cells into multi-member vs
singleton groups, `group_it=True` only the multi set, keep singletons as plain
per-cell series (no spread), then merge Plotly traces / export frames.

**Follow-up (#39):** merging those two Plotly figures with bare `add_trace` puts
singleton series on the wrong facet — averaged (long) and per-cell (wide)
collections assign different subplot ids (`x`/`y`/`x2`/…) to the same
`variable`. App remaps secondary traces onto the base figure's
variable→axis map before merge. Ideal upstream: stable facet axis ids (or a
merge helper) so long and wide summary plots share subplot identity by
`variable`.

**Wish:**
1. Average groups that have ≥ 2 cells and leave singletons as ordinary (non-spread)
   series in the same collection — not all-or-nothing.
2. `Collection.meta.grouped: bool` (or `collection.is_grouped`) so callers can
   adapt UI/labels without inspecting columns.
3. Stable facet subplot ids across long (averaged) vs wide (per-cell) summary
   plots for the same column set.

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

cellpy-simple-gui #32 layered **light/dark theme tokens** and curated **colorways**
onto that restyle, and registers cellpy's collector templates via
`make_collector_templates` (already done inside cellpy's plot path). Those
templates still don't cover app needs for: compact right-hand legend + long-name
truncation, facet-strip shortening, per-theme paper/plot colors, or a discrete
colorway switch independent of the science plot family.

**Wish:** a first-class theme/label/height/colorway hook (or a `FigureSpec` the
caller can pass) so the returned figure drops cleanly into an app without
post-processing. `make_plotly_template` / collector templates help axes, not the
full app chrome contract.

## 12. 🟢 Per-panel y-limits on collected summary facets

`match_axes=False` already gives independent auto-scale (cellpy-simple-gui #2
forwards it as `share_y`). Fixed **per-facet-row** ranges ship via cellpy
`y_ranges={variable: [lo, hi]}` (#804, 2.1.1.post2+); the app exposes them as
`SummaryPlotSpec.y_ranges` + summary UI widgets (#54). Older notes about
`AxisSpec` / `ce_range` / global `range_y` remain historical background.

### 12b. 🟠 `spread_plot` ignores `share_y` / `match_axes`

`summary_plotter` resolves `share_y` / `match_axes` and passes `match_axes=` into
`_cycles_plotter`, but the **spread** path (`spread_plot` / mean±std bands used
when a group-averaged frame is plotted with `spread=True`) never links facet
y-axes — `matches` stays unset even when `match_axes=True`. Apps that offer
“Share y-scale” together with “Group avg + Spread” must re-apply
`yaxisN.matches = "y"` after `collection.plot` (cellpy-simple-gui #47).

**Wish:** honour `share_y` / `match_axes` in `spread_plot` the same way the
non-spread summary path does.

**Wish / tracking:** https://github.com/jepegit/cellpy/issues/804

## 13. 🟠 No app-friendly static figure export on the collect path

`collection.plot()` is the right way for an app to get a Plotly figure, but there
is no matching collect-level API to turn that figure into PNG / SVG / PDF bytes.
`Collection.save(...)` is **data-only** (parquet/csv/json/xlsx). The kaleido-based
helper that does exist — `cellpy.utils.plotutils.save_image_files` — lives outside
collect, writes to **disk**, spawns a **subprocess** around `fig.write_image`, and
prints status to stdout. That fits notebooks/scripts; it does not fit a desktop
or FastAPI app that wants `(bytes, media_type)` for a download response (and a
clear error when kaleido is missing).

This is exactly the kind of gap this app is meant to surface: the science path
(`from_cells` → `collect_summaries` → `.plot()`) is great, then static export
falls off the paved road and each app reinvents Plotly/kaleido wiring.

**Wish:** something on the collect / plotting surface, e.g.

```python
collection.to_image("svg")           # -> bytes
# or
fig = collection.plot(...)
cellpy.plotting.write_image(fig, "pdf")  # -> bytes, raises if kaleido missing
```

Same formats users expect from kaleido (`png` / `svg` / `pdf`), in-memory, no
subprocess or cwd side effects. Optional: `Collection.save(..., formats=("svg",))`
that saves the *plot* next to the data — but bytes-first matters more for apps.

*(cellpy-simple-gui #27 — will call `fig.write_image` directly until this exists.)*

## 14. 🟠 `.h5` auto-picks cellpy format over raw instrument loaders

`cellpy.get(..., auto_pick_cellpy_format=True)` (the default) treats `.h5` /
`.hdf5` as native cellpy files whenever `instrument` is not exactly
`arbin_sql_h5`. Other Arbin SQL variants (or a missing instrument) then hit the
native reader and fail with `No object named data_df in the file` — easy to
misread as a corrupt file. cellpy already special-cases `arbin_sql_h5`, but apps
that always pass an explicit instrument still need
`auto_pick_cellpy_format=False` for defense in depth.

**Workaround (cellpy-simple-gui #41):** `load_raw` always sets
`auto_pick_cellpy_format=False`; Load cells stays on the native path and the UI
hints that Arbin SQL HDF5 belongs under Import raw.

**Wish:** when `instrument=` is set, never auto-pick cellpy format from suffix
(or document that callers must disable it for every raw `.h5` loader).

## 15. 🟢 Cycles collector facet strips still use raw `cycle_num=` / `cell=`

#801 / post4 pretty-prints **summary** facet labels (no more
`variable=charge_capacity_gravimetric` on strips; axis titles are human-readable).
The **cycles** family (`layout="per_cell"` / `"per_cycle"`, legacy
`fig_pr_cell` / `fig_pr_cycle`) still annotates facets as `cycle_num=1`,
`cell=demo`, etc. Axis titles for capacity/voltage are already fine; only the
facet strips look unfinished next to summary plots.

Surfaced while adding the multi-cell Cycles tab in cellpy-simple-gui #55 —
same `collection.plot(family_kind="cycles", layout=…)` path, no app restyle for
those annotations yet.

**Wish:** apply the same pretty-label pass to cycles (and other non-summary)
collected layouts — e.g. `Cycle 1` / cell label only — so apps get consistent
chrome without per-family string scrubbing. Optionally document that `layout=`
is preferred over legacy `method="fig_pr_*"` in `cycles_plotter` docs.

## 16. 🟢 ICA plotter cannot show charge and discharge together

`cellpy.utils.ica.dqdv(..., direction="both")` (and therefore `collect_ica`,
which calls `dqdv` with the default) returns a tidy frame with both half-cycles
(`direction` column = `charge` / `discharge`). The collected **plot** path does
not: `ica_plotter` only accepts `direction="charge"` or `"discharge"` and
silently coerces anything else to `"charge"` (with a `print`).

Apps that want a single figure with both directions must merge two plot calls
themselves. cellpy-simple-gui #56 therefore exposes only Charge | Discharge in
the Cell explorer dQ/dV UI.

**Wish:** honour `direction="both"` in `ica_plotter` / `collected_plot` (e.g.
two series or grouped legend entries per cycle), and prefer a logger warning
over `print` when coercing invalid values.

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
