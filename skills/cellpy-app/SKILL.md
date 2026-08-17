---
name: cellpy-app
description: >-
  Write Python that uses cellpy (>= 2.1.2) to load battery cell files, build
  Collections, plot them and export data or figures. Use when the task involves
  cellpy, CellpyCell, cellpy.get, collect_summaries / collect_cycles /
  collect_ica / collect_dva, the cellpy plot family registry, battery cycling
  data, dQ/dV or dV/dQ, or building an app or script on top of cellpy. Contains
  the API surface and the traps that produce plausible-but-wrong output.
---

# Building on cellpy

cellpy is a battery-data library. Most of what goes wrong with it **produces
plausible output rather than an error**, so the traps below matter more than the
API listing — a chart that looks right is the normal failure mode here.

Full signatures for ~44 calls: [`reference/api-reference.md`](reference/api-reference.md).

## The shape of every cellpy program

```python
import cellpy
from cellpy.collect import collect_summaries, from_cells

cell = cellpy.get(filename="cell.res", instrument="arbin_res", mass="0.47 mg")
batch = from_cells({"cell A": cell})              # a real Batch, no journal on disk
collection = collect_summaries(batch, columns=("discharge_capacity_gravimetric",))
figure = collection.plot()                        # a plotly Figure
csv = collection.data.write_csv()                 # collection.data is polars
```

**Do not assemble frames by hand.** `from_cells` is the bridge; once cells are in
a `Batch`, grouping, group averaging, spread bands, per-cell cycle isolation and
multi-format export are cellpy's job. Reimplementing them is the most expensive
mistake available.

## Pick the collector by what you are plotting

| Want | Call | Options |
|---|---|---|
| capacity / CE / IR / voltages vs cycle | `collect_summaries(batch, columns=…)` | `SummaryOptions` |
| voltage curves for chosen cycles | `collect_cycles(batch, options=…)` | `CurveOptions(cycles=…, mode=…, method=…)` |
| dQ/dV | `collect_ica(batch, options=…)` | `IcaOptions(cycles=…, voltage_resolution=…)` |
| dV/dQ | `collect_dva(batch, options=…)` | `IcaOptions(...)` |

All four return a `Collection`: `.data` (polars), `.plot()` (plotly Figure),
`.save()`, `.to_image()`, `.to_wide()`, `.is_grouped`.

## Traps

**A density film is a `kind=`, not a `layout=`.** Always write:

```python
figure = collection.plot(kind="film", layout="per_cell")
assert {t.type for t in figure.data} == {"histogram2d"}   # not scattergl
```

`kind="film"` is correct on every version. On cellpy **2.1.2 and earlier**,
`layout="film"` silently drew *lines* instead, and `layout="anything_misspelt"`
did too — no error, no warning, a perfectly plausible figure. Fixed in **2.1.3**
([cellpy#874](https://github.com/jepegit/cellpy/issues/874)): `layout="film"` is
now an alias and unknown layouts raise. A legacy `method="film"` spelling also
works; prefer `kind=`. Assert on the trace type either way — "it drew something"
is not a test.

**dQ/dV plots show one half-cycle by default.** `collect_ica` keeps both
directions; the plotters draw `charge` unless told otherwise — lines and film
alike — so the chart shows a fraction of the rows you collected and says
nothing. `direction` is an argument to `plot()`, **not a field on `IcaOptions`**,
which is why looking at the options dataclass suggests there is no control:

```python
collection.plot(kind="film", layout="per_cell", direction="both")
```

(`histscale="abs-log"` is also worth setting for dQ/dV films; the unscaled
default is rarely right.)

**Availability is judged on `summary_options().columns`, not `columns()`.**
A plot family's `columns(hdr)` includes columns the *collector* manufactures
(`*_cv`, `mod_01_*`). Checking those against the data reports "your data is
missing columns" for families that work fine.

```python
from cellpy.plotting import registry

hdr = cell.schema.summary                      # the summary column vocabulary
family = registry.get("capacities_gravimetric")
collection = collect_summaries(batch, options=family.summary_options(hdr))
```

**Build plot menus from the registry, filtered by entry point.**
`registry.families(entry_point="summary_plot")` — without the filter you list
`raw`, `ica`, `dva` and `cycles`, which can never work in a summary menu.

**`mass` is not cosmetic.** Omit it and it defaults to 1.0 mg; every
`*_gravimetric` column is then wrong by a factor of the real mass, with no error.
Unit strings are accepted and clearer: `mass="0.47 mg"`.

**`from_cells` silently drops values that are not cells.** A path, an `int`,
anything — no exception, no warning. Note that `example_data.rate_file()` returns
a *path* while `example_data.cellpy_file()` returns a *cell*. Validate the
mapping if you build it dynamically.

**A column the data lacks collects to nothing**, drawing an empty chart rather
than raising. Check `cell.data.summary.columns` first.

**Grouping changes the schema.** `group_it=True` replaces `cell` and your column
with `variable` / `mean` / `std`. Branch on `collection.is_grouped`.
`plot(spread=True)` only means anything when it is true.

**`cycle_info_plot` needs `get_axes=True`** or it returns `None` on the plotly
backend. **`raw_plot` needs `max_points`** — one demo cell is 7.35 MiB of figure
JSON without it, 0.18 MiB with — and it downsamples silently.

**`cellpy.read_meta` reads cellpy files only.** A raw file gives an HDF5
superblock traceback, not a useful message.

**polars vs pandas.** `collection.data` is polars; `cell.data.summary`,
`cell.data.raw`, `cell.data.steps` and `cell.get_cap()` are pandas. Cross with
`.to_pandas()` at the edge of your code.

## Configuration and threads

- `config.get_config()` resolved settings · `config.sources()` per-key provenance
  · `config.active_config_file()` which file won.
- `config.override(...)` is scoped **per thread and per asyncio task**.
  `config.reload(...)` is **process-global**.
- Environment: `CELLPY_<SECTION>__<FIELD>`, e.g. `CELLPY_PATHS__OUTDATADIR`.
- Never write the user's `cellpy.toml` — it is shared with their notebooks and
  CLI. If you pin settings to a project, write an allow-list (`reader`, `units`,
  `defaults`); omitting `instruments` and `db` means the file *structurally*
  cannot hold a credential.
- Some path defaults are **relative** and resolved against the process cwd, and
  `examplesdir` is read at import time and falls back into `site-packages` if the
  directory does not exist. Anchor writable paths before anything imports
  `cellpy.utils.example_data`.

## Getting started fast

`cellpy.utils.example_data.cellpy_file()` returns a loaded 304-cycle demo cell,
downloaded once and cached. Use it to check an approach before touching real
data.

## Where the longer answers are

- Task-shaped guides, every code block executed in CI:
  <https://github.com/cellpy/cellpy-simple-gui/tree/main/docs/guides>
- A complete app in one file:
  <https://github.com/cellpy/cellpy-simple-gui/blob/main/examples/starter/app.py>
- Every known rough edge with its upstream issue:
  <https://github.com/cellpy/cellpy-simple-gui/blob/main/CELLPY_PAINPOINTS.md>
