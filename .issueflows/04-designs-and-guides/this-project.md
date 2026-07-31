# cellpy-simple-gui

## What this project is

**cellpy-simple-gui** (GitHub: [cellpy/cellpy-simple-gui](https://github.com/cellpy/cellpy-simple-gui))
is an MVP desktop app for exploring battery cell data with **cellpy ≥ 2.1.1.post4**.
It is the successor to the Streamlit demo in `cell_processor_app`: same local,
browser-feel workflow, but with a real installable shell, a thin FastAPI backend,
and a reusable pure-Python core. Intended for single-user / offline lab use.

Design rationale and the longer CellProcessor 2.0 plan live in
[`cellprocessor-v2-design.md`](cellprocessor-v2-design.md). Upstream cellpy
friction notes (mostly fixed in 2.1.1) are in repo-root `CELLPY_PAINPOINTS.md`.

## Stack / runtime

- **Language:** Python **≥ 3.13** (pinned in `.python-version`).
- **Package manager:** **`uv`** exclusively (`uv.lock`). Never bare `python`,
  `pip`, or `poetry`.
- **cellpy:** `cellpy>=2.1.1.post4` (needs `pandas>=3.0`). Legacy `.h5` via `tables`.
  Prefer collect plot chrome knobs (`layout_updates`, pretty labels,
  `height_per_panel`) over growing app `_restyle`; see
  [`cellpy-delegation-inventory.md`](cellpy-delegation-inventory.md).
- **Backend:** FastAPI + uvicorn on `127.0.0.1` with a per-launch token
  (cookie / header / `?token=`).
- **Jobs:** thread-pool `JobManager` (`api/jobs.py`) with SSE progress/cancel
  (MVP chose threads over the design doc's ProcessPool).
- **Frontend:** Jinja2 shell + Alpine.js + vendored Plotly.js (offline). Dark/light themes.
- **Desktop shell:** pywebview (`desktop.py`); `--server` opens a normal browser instead.
- **Domain:** Pydantic models; in-memory `Library` is the runtime source of truth;
  portable project folders under `~/.cellpy_simple_gui/projects/` (manifest +
  `.cellpy` files) — not the design doc's SQLite registry.
- **External tools:** `git`, `gh` for issue-flow; Windows Arbin `.res` uses the
  Access ODBC driver (`sqlalchemy-access`) — **no mdbtools** in this app.

## How to run / test

Always run from **this repo root** (`cellpy-simple-gui/`), not the multi-root
workspace parent — sibling repos have their own trees and can pollute collection.

```bash
uv sync --extra dev
./run                                 # native window (includes --extra export / kaleido)
./run --server                        # browser tab
uv run --extra export cellpy-simple-gui   # same as ./run
uv run pytest                         # unit + FastAPI integration (+ e2e skips if no Playwright)
```
Optional kaleido static export: `uv sync --extra export`.

Optional Playwright GUI smoke (`tests/test_gui_playwright.py`, marker `e2e`)
against `--server` mode — not pywebview:

```bash
uv sync --extra dev --extra e2e
uv run playwright install chromium
uv run pytest -m e2e
```

No ruff/formatter gate is configured in `pyproject.toml` yet — do not invent one.

## Conventions

- **Branches:** issue work on `<N>-<short-slug>`; default branch is `main`.
- **cellpy boundary:** only `core/cellpy_adapter.py` and `core/collect.py` import
  cellpy. The UI and routers never import cellpy. Prefer cellpy's own
  `collect` / `plotting` APIs over reimplementing science logic.
- **Prefer cellpy APIs that exist in ≥2.1.1:**
  `cellpy.collect.from_cells(...)`, `cellpy.list_instruments()`,
  `Collection.is_grouped`, `CurveOptions(mode=, method=)`,
  `cellpy.plotting.registry.families()`, `cell.data.summary` (not deprecated
  `get_summary`), `cell.get_cap(cycle=, mode=, method=)`.
- **Instruments:** discover at runtime via `list_instruments()` / 
  `instrument_configurations()` — do not hard-code loader names. Instrument
  names = module names under `cellpy/readers/instruments`.
- **Multi-root workspaces:** for at least one of the developers,
- this repo sits beside `cell_processor_app` and `cellpy_streamlit_installer`.
  See [`multi-repo-workspaces.md`](multi-repo-workspaces.md).
  Resolve the project root before `git`/`gh`/`.issueflows/` work; always
  `uv run` / `pytest` from *this* directory.

## Release & version bump

**Static version (uv).** `[project] version` lives in `pyproject.toml`
(currently `0.1.0`). Bump with:

```bash
uv version --bump <level>   # major | minor | patch | alpha | beta | rc | …
```

There is no `HISTORY.md` yet — `/iflow-close` changelog updates are skipped
until one exists at the repo root. No git-tag-derived versioning.

## Motivation

The app is meant to inspire other users of cellpy to make their own apps. We
also use the development of this app to find pain-points in the cellpy library.

It should be easy to make apps based on cellpy. 

When we find stuff that, if implemented in cellpy, would improve the experience for
app-builders, we write it down in CELLPY_PAINPONTS.md and offer to create issues in the
cellpy repo.

## Entry points

- **CLI / app:** `cellpy-simple-gui` → `cellpy_simple_gui.__main__:main`
  (`desktop.py` or `--server`).
- **Package root:** `src/cellpy_simple_gui/`
  - `core/` — models, library, adapter, collect, plotting, projects, ingest helpers, export
  - `api/` — FastAPI app, jobs, routers (`cells`, `plots`, `export`, `jobs`, `projects`, `ingest`, `system`)
  - `web/` — Jinja templates + static (Alpine, Plotly, CSS)
- **Read first:** `README.md`, this brief, [`cellprocessor-v2-design.md`](cellprocessor-v2-design.md),
  then `CELLPY_PAINPOINTS.md` when touching cellpy integration.

## Non-goals / known limitations

- Not multi-user / hosted / auth / cloud storage (single-user desktop).
- Not feature-parity with every Streamlit demo page yet (MVP covers load,
  ingest, summary / cycles collector / cell explorer, journal edits, projects,
  export).
- **Next major gap:** Windows installer packaging (PyInstaller + InnoSetup,
  WebView2) — reuse patterns from sibling `cellpy_streamlit_installer`.
- SQLite job/project registry, ProcessPool workers, and full batbase-as-native
  journal story from the 2.0 design are **not** implemented in the MVP; see
  the as-built section in the design guide before "restoring" them casually.
