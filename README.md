# cellpy simple gui

A small **desktop app** for exploring battery cell data with
[**cellpy**](https://github.com/jepegit/cellpy) (**≥ 2.1**).

It runs a local [FastAPI](https://fastapi.tiangolo.com/) backend inside a native
window (via [pywebview](https://pywebview.flowrl.com/)).

![Cycle summary](docs/img/summary_collect.png)

<p align="center">
  <img src="docs/img/cell_collect.png" width="49%" alt="Cell explorer — cellpy cycle curves" />
  <img src="docs/img/manage_cells.png" width="49%" alt="Manage cells modal" />
</p>

---

## Features

- **Zero-setup demo** — one click loads three bundled example cells (no files needed).
- **Load your own** `.cellpy` / legacy `.h5` files.
- **Import raw instrument files** — Arbin `.res`, Maccor (text), Neware, PEC and more are
  processed into cellpy cells with a metadata step (mass / area / nominal capacity / cycle
  mode). One-click bundled raw demos too.
- **Save & reopen projects** — explicit Save (not autosave) writes the loaded set plus
  grouping / labels / selection into a portable project folder; reopen later. The project
  tag shows when you have unsaved edits (`name*`), and **Close** clears the current
  session after confirmation. Re-saving only rewrites cells whose *data* changed —
  renaming or regrouping is roughly **10× faster** than a full write, because
  those live in the manifest, not in the `.cellpy` files.
- **Cycle summary** across many cells — built with cellpy's own
  `collect_summaries` + plotting, with a **plot-type selector** (capacity + CE,
  capacity, coulombic efficiency, cumulated CE, end voltages, internal
  resistance, C-rate, capacity loss), a gravimetric / areal / absolute basis,
  optional group averaging with a mean ± std spread band, and independent or
  shared y-scales.
- **Cell explorer** — cellpy's `collect_cycles` voltage–capacity curves for any
  set of cycles (gravimetric / areal / absolute, method), with per-cell metric
  tiles. Switch the same cycles to **dQ/dV** (incremental capacity) or
  **dV/dQ** (differential voltage), charge / discharge / both.
- **Cycles collector** — the same three curve types across *every selected
  cell*, laid out per cycle or per cell, or as a **film** (density) plot.
- **Load data lots of ways**: bundled demo cells, `.cellpy` / `.h5` files,
  **native cellpy batch journals** (`.json`), or your own **project folders** —
  with **glob patterns** (`*si*.h5`, capped at a configurable max) and, in the
  desktop app, **native file pickers**. Journal load failures surface as toasts
  instead of a stuck spinner.
- **Editable cell list** (the "journal"): rename, group, select/deselect, remove —
  plus a **Manage cells** modal (filter/sort, select-by-group, remove all).
- **Instruments discovered from cellpy** at runtime (not hard-coded), with each
  loader's sub-models.
- **Clear feedback**: toast notifications for loads, saves, opens, exports, and
  errors (including corrupt journals).
- **Background loading** with live progress (SSE) — the UI never freezes.
- **Export** collected data to **CSV / Excel / Parquet / JSON**, and charts as
  **PNG / SVG / PDF** from **Export ▾** (server-side via kaleido — install with
  `uv sync --extra export`); the chart toolbar camera still saves a quick PNG.
- **Light & dark themes.**
- **Colorized terminal logging** via loguru (`CSG_LOG_LEVEL`, default `INFO`).

## Install

Requires **Python ≥ 3.13**. With [uv](https://docs.astral.sh/uv/):

```bash
uv tool install "cellpy-simple-gui[desktop]"
cellpy-simple-gui
```

Or run it once without installing anything:

```bash
uvx --from "cellpy-simple-gui[desktop]" cellpy-simple-gui
```

pipx works too: `pipx install "cellpy-simple-gui[desktop]"`.

The `[desktop]` extra is what gives you the **native window**. Leave it off and
you get a fully working app that opens in your browser instead — which is what a
server wants, and why it is an extra rather than a dependency.

Two heavier routes, if you would rather not have Python in the picture:

- **Windows installer** — 178 MB, no admin, Start-menu entry.
  See [`docs/windows-installer.md`](docs/windows-installer.md).
- **Container** — `docker compose up`. See [`docs/deployment.md`](docs/deployment.md).

---

## Quick start (from a clone)

Requires **Python ≥ 3.13** and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --extra desktop
```

The native window lives in the `desktop` extra so a served instance need not
install GUI libraries. Plain `uv sync` gives you a fully working app that opens
in your browser instead.

Then from this folder:

```bash
run                 # Windows (cmd / PowerShell)
./run               # macOS / Linux / Git Bash
```

That opens the app in a native desktop window. Prefer your normal browser?

```bash
run --server              # local server + browser tab
run --server --no-open    # headless: just serve
```

The helpers use `uv run --extra export --extra desktop`, so figure export and the
native window both work. Equivalent without them:
`uv run --extra export --extra desktop cellpy-simple-gui` (same flags).
Then click **Load demo cells** and explore.

### Build the Windows installer

```powershell
pwsh packaging/build_installer.ps1
```

Produces a ~178 MB per-user installer: no admin, Start-menu entry, clean
uninstall that leaves your projects alone. It is **unsigned**, so SmartScreen
will warn on first run — [`docs/windows-installer.md`](docs/windows-installer.md)
explains exactly what you will see, why, and what fixing it costs, along with
where the app writes its logs when something goes wrong.

Cutting a release of any of the three artefacts:
[`docs/releasing.md`](docs/releasing.md).

### Run it as a server

```bash
docker compose up --build      # or: docker build -t cellpy-simple-gui .
```

One container serves **one person** — the library, the job manager and cellpy's
config session are process-global, by design. The per-launch token is **not**
authentication: put it behind a reverse proxy with TLS and real auth, or keep it
on a network you already trust. [`docs/deployment.md`](docs/deployment.md) has
the full story, including the things that bite (volume ownership, cellpy's own
directories, and why server-side figure export is not in the image).

### Developer mode

```bash
run --dev                 # or set CSG_DEV_MODE=1
```

The regular UI shows a curated set of plot types, because cellpy registers far
more than are useful on any one dataset. Developer mode adds **every summary
family cellpy registers**, grouped by whether the loaded cells can actually plot
them — the rest are listed but disabled, showing which summary columns are
missing rather than rendering a blank chart. Availability comes from cellpy
itself (`family.summary_options()`), so families whose columns the *collector*
builds — CV splits, the full-cell standards — are offered rather than hidden. It
also raises the glob/batch file cap (10 → 500) for stress-testing. A **DEV**
badge marks the session.

Two extra Cell-explorer views appear alongside the regular ones:

| View | What it shows |
|---|---|
| **Raw traces** | The raw time series (voltage/current/capacity, or all of it) |
| **Raw + step/cycle info** | Raw traces annotated with step and cycle boundaries |

Raw data is big — 155k rows for a single demo cell — so **Max points** caps what
is drawn (cellpy does the downsampling itself since 2.1.2,
[#867](https://github.com/jepegit/cellpy/issues/867)) and the chart says when it
applied: *"showing 1,882 of 155,754 points"*. For raw *data* rather than a
picture, use **Export cells → csv**.

Clicking the **DEV** badge opens **Diagnostics**:

- **Logs** — a live tail of the last 2000 records, filterable by level. cellpy's
  own records arrive here too (they go through stdlib logging), so a failed load
  can be diagnosed without opening `cellpy_debug.log`.
- **Jobs** — every job this session with how long it waited for a worker and how
  long it ran.

**copy** puts either view on the clipboard as plain text, ready for a bug report.

Off by default and not reachable from the UI: regular users get the curated set.

> First run downloads a few small example cells from the cellpy example-data
> repository (then cached). Everything else is fully offline.

![Projects](docs/img/projects_dark.png)

![Plot types](docs/img/plot_types.png)

## Projects on disk

A project is a portable folder — move it, zip it, share it:

```
<project>/
├── project.json      # manifest: name, timestamps, versions, per-cell grouping/labels/selection
├── cellpy.toml       # optional: cellpy settings pinned to this project
└── data/
    ├── c1.cellpy     # every loaded cell saved as a self-contained cellpy file
    └── c2.cellpy
```

Projects live under `~/.cellpy_simple_gui/projects/` by default; **Save** writes the
current set there and **Open** restores it (physical quantities come from the
`.cellpy` files, organisational metadata from the manifest). Changes in the UI
are **not** written until you Save.

That split is also why Save is quick. Re-saving reuses a `.cellpy` file whenever
the cell it holds provably has not changed — nothing edited it since it was
read, the file is still there, and its size and timestamp still match. Renaming
or regrouping touches only `project.json`. Editing mass, area, nominal capacity
or cycle mode rewrites the summary, so those cells are written out again; if
anything is uncertain, the file is rewritten. Save-As always produces a complete
project.

### Moving the data directory

`CSG_DATA_DIR` decides where projects live. It defaults to
`~/.cellpy_simple_gui`, so desktop installs need nothing; a container points it
at a volume:

```bash
CSG_DATA_DIR=/data cellpy-simple-gui --server --no-open
```

`~` and relative paths are expanded and resolved, and reading the setting never
creates anything — whoever writes creates what it needs.

**cellpy keeps its own directories**, separate from the app's, and they default
under `$HOME` too. Anything running where `$HOME` is not persistent should place
them deliberately. Every field under `[paths]` has an environment override,
`CELLPY_PATHS__<FIELD>`:

```bash
CELLPY_PATHS__CELLPYDATADIR=/data/cellpy/cellpyfiles
CELLPY_PATHS__OUTDATADIR=/data/cellpy/out
CELLPY_PATHS__EXAMPLESDIR=/data/cellpy/examples   # bundled demo cells cache here
CELLPY_PATHS__FILELOGDIR=/data/cellpy/logs
```

Overrides apply per field, so setting one leaves the rest alone. The **cellpy
version badge** in the app shows every setting and which layer it came from,
which is the quickest way to confirm a deployment is reading what you think.

### Local vs served: what the app may touch

Typing `D:\data\*.res` into the app is the point of a desktop tool. Answering
requests over a network with that same freedom is arbitrary read and write on
the **host**, behind nothing but a per-launch token — so the app has two modes,
chosen by the bind address:

| | bound to | paths |
|---|---|---|
| **local** | loopback | anywhere you can reach, as always |
| **served** | anything else | inside `CSG_DATA_DIR` only |

In served mode, absolute paths, `..`, drive letters, UNC paths and symlinks that
point outward are all refused — the *resolved* location is what gets checked, so
a link that looks innocent does not get through. Globs are rooted at the data
directory and their results filtered, because `**` through a symlinked directory
is the classic way out.

One case the bind address gets wrong: an instance on loopback **published by a
reverse proxy** looks local from inside, because the proxy connects from
loopback. Force it:

```bash
CSG_ALLOW_HOST_PATHS=0
```

`/api/system/capabilities` reports `host_paths_allowed` and `sandbox_root`, so
you can confirm which rules an instance is running under.

> A served instance currently reads files that are already inside its data
> directory — mount your data there. Browser upload is
> [#133](https://github.com/cellpy/cellpy-simple-gui/issues/133).

### Per-project cellpy settings

Drop a `cellpy.toml` next to `project.json` and the app activates it as cellpy's
**project** configuration layer whenever that project is open — so the project
pins the settings its data was analysed with (cycle mode, units, defaults)
instead of being silently re-interpreted under whatever your global config says
today:

```toml
[reader]
cycle_mode = "cathode"

[units]
mass = "g"
```

A **cellpy.toml** chip appears next to the project name while those settings are
active; closing the project restores your own configuration. Settings never leak
from one project to the next. Click the chip (or the cellpy version badge) to see
every setting and which layer it came from — defaults, your user `cellpy.toml`,
the project file, or the environment.

Rather than writing the file by hand, open that panel with a project loaded and
hit **Pin settings to project**: it captures the `reader`, `units` and
`defaults` currently in effect. Only those sections are written — `paths` would
bake your machine's directory layout into a folder meant to be portable, and
leaving out `instruments`/`db` means the file structurally cannot contain a
credential.

The app never writes your user `cellpy.toml`; that file belongs to you and is
shared with your notebooks and the `cellpy` CLI.

## How it is built

Three layers, each testable on its own. The UI never imports cellpy; the core
never imports the web framework.

```
┌──────────────────────────────────────────────────────────────┐
│  desktop shell (pywebview window)                             │
│    └── web/  Alpine.js + Plotly.js  (served by the backend)   │
├──────────────────────────────────────────────────────────────┤
│  api/   FastAPI (127.0.0.1 + per-launch token)                │
│         routers · JobManager (threads + SSE progress)         │
├──────────────────────────────────────────────────────────────┤
│  core/  pure Python — no web imports                          │
│         models · library · plotting · export                  │
│         cellpy_adapter.py  ← the ONLY module that imports cellpy
└──────────────────────────────────────────────────────────────┘
                              │
                          cellpy ≥ 2.1
```

```
src/cellpy_simple_gui/
├── core/
│   ├── cellpy_adapter.py   # every cellpy call lives here (get, summary, get_cap, example_data)
│   ├── models.py           # Pydantic domain models (CellMeta, SummaryPlotSpec, …)
│   ├── library.py          # in-memory library of loaded cells = source of truth
│   ├── collect.py          # bridges the library into cellpy.collect / .plotting (from_cells)
│   ├── plotting.py         # thin: delegates figures to cellpy via collect.py
│   ├── projects.py         # save/open portable project folders (manifest + .cellpy files)
│   ├── files.py            # glob/path expansion with a max cap + messages
│   ├── paths.py            # the sandbox: what a served instance may read and write
│   ├── uploads.py          # files brought in through the browser
│   └── export.py           # csv / xlsx / parquet / json from cellpy collections
├── api/
│   ├── app.py              # FastAPI factory + index route
│   ├── jobs.py             # tiny thread-pool JobManager (progress + cancel)
│   └── routers/            # cells · plots · export · jobs · projects · ingest · system
├── web/                    # templates/ (Jinja) + static/ (css, js, vendored Plotly & Alpine)
├── logging_setup.py        # loguru terminal logging + stdlib bridge
├── server.py               # uvicorn-in-a-thread helper
├── desktop.py              # pywebview launcher
└── __main__.py             # entry point (desktop / --server)
```

**Powered by cellpy, not around it.** Summaries, grouping (incl. group averaging
with spread), per-cell cycle curves, the plots and the multi-format export are all
produced by cellpy's own `collect` / `plotting` subsystems. On **cellpy ≥ 2.1.1**
the app feeds them a real `Batch` via `cellpy.collect.from_cells(...)` built from
the in-memory library (`collect.py`), and discovers instruments via
`cellpy.list_instruments()`. The cellpy surface stays isolated to
`cellpy_adapter.py` + `collect.py`.


## Building your own cellpy app

This app is a reference implementation. It is a poor thing to start *from* — at
~8,000 lines, most of what you would read is machinery you have not decided you
want yet.

[`examples/starter/`](examples/starter/) is the starting point instead: one file,
~340 lines, that loads cells, builds a cellpy `Collection`, plots it and exports
the numbers, and nothing else.

```bash
uv run examples/starter/app.py     # then open http://127.0.0.1:8000
```

It carries its own dependencies in a PEP 723 header, so `uv run --script app.py`
also works once you have copied it somewhere else — which is what it is for. See
[`examples/starter/README.md`](examples/starter/README.md) for the four cellpy
calls it is built from, how to add a plot, and where in this repository to look
when you outgrow it.


## Development

```bash
uv sync --extra dev
uv run pytest            # core unit tests + FastAPI integration tests
uv run pytest -m essential   # critical-path subset (also run in CI)
```

The suite passes without the `desktop` extra — that is the point of it being an
extra, and one test skips accordingly. Add `--extra desktop` to run that one too.

Optional Playwright GUI smoke tests (server/browser mode, not pywebview):

```bash
uv sync --extra dev --extra e2e
uv run playwright install chromium
uv run pytest -m e2e
```

Without the `e2e` extra / Chromium browsers, those tests skip so a plain
`uv run pytest` stays green.

GitHub Actions runs the `essential` marker. One workflow decides internally
whether the change touched code, so every PR gets exactly one `essential` check
run — and a green one means either "tests passed" or "no code changed", never
"a second workflow reported first". If the base commit cannot be resolved, it
runs the tests rather than guessing.

Optional static figure export (**Export ▾ → Figure → PNG / SVG / PDF**, via kaleido):

```bash
uv sync --extra export
```

Without that extra, data export still works; figure formats show a toast pointing
at the install command above.

### Why we develop this app

The app is meant to inspire other users of cellpy to make their own apps. We
also use the development of this app to find pain-points in the cellpy library.

Already now, building this surfaced a number of cellpy rough edges, filed upstream as
[jepegit/cellpy#785–#791](https://github.com/jepegit/cellpy/issues/785) — **most were fixed in cellpy 2.1.1**. The full write-up and per-item status is in
[CELLPY_PAINPOINTS.md](CELLPY_PAINPOINTS.md).

## Status

This is an MVP / reference implementation

Done: load `.cellpy`/`.h5` files, **raw-file ingestion** (Arbin `.res` / Maccor / Neware /
PEC → cellpy), cycle-summary & cell-explorer plotting, editable cell list + Manage cells
modal, CSV/Excel/Parquet/JSON export with feedback, **save/open/close portable projects**,
batch-journal loading with error toasts, loguru console logging, and essential-test CI.

> Arbin `.res` loads on Windows through the Access ODBC driver (no separate mdbtools needed
> in this environment). Instruments needing extra engines will surface a clear error.

### Future plans

- packaging into a Windows installer (PyInstaller + InnoSetup, bundling WebView2).
- show-case more of the plots

## License

See [LICENSE](LICENSE).
