# CellProcessor 2.0 — design guide (for agents)

Working design for replacing the Streamlit `cell_processor_app` with a
maintainable desktop app on **cellpy ≥ 2.1**. This file is the issue-flow copy
agents should read; the longer original draft also lives at the workspace root
as `cellprocessor_v2_design.md` (outside this git repo).

**Status:** design + MVP in flight. **`cellpy-simple-gui` is the MVP
implementation** of this architecture — not a separate product.

---

## 1. Goals & locked decisions

**Goals**

1. **State & reliability** — no fragile Streamlit `session_state`; durable
   project state and real errors.
2. **Long-running work** — raw-file load/process in the background with
   progress + cancel.
3. **Separation of concerns** — cellpy logic out of the UI into a reusable core.
4. **Packaging & updates** — Windows installer for non-technical lab users.

**Locked decisions**

| Question | Decision |
|---|---|
| Who / where | Single-user desktop, data local, offline-capable |
| UI | Local web UI in a desktop shell (browser feel, real app) |
| cellpy | Target ≥ 2.1 (app pins ≥ 2.1.1) |

**Non-goals (for now):** multi-user hosting, auth/RBAC, cloud DB, mobile.

---

## 2. Target architecture

Three layers. **UI never imports cellpy; core never imports FastAPI/UI.**

```
desktop shell (pywebview)
  └── web UI  ←→  local FastAPI (127.0.0.1 + launch token)
                    ├── JobManager (progress via SSE)
                    └── services / persistence
                          └── core (adapter is the ONLY cellpy import*)
                                └── cellpy ≥ 2.1
```

\*MVP also lets `core/collect.py` call cellpy's `collect` / `plotting` — see §5.

**Why this shape**

- pywebview + local FastAPI = browser feel + installable `.exe`, no exposed LAN.
- Pure-Python core = testable, scriptable; cellpy migration concentrated.
- Backend owns durable truth; frontend keeps only view state.

---

## 3. Technology choices (design vs MVP)

| Layer | Design recommendation | MVP as-built (`cellpy-simple-gui`) |
|---|---|---|
| Language | Python 3.12 | **Python ≥ 3.13** |
| Backend | FastAPI + uvicorn on localhost | Same + per-launch token |
| Frontend | HTMX + Alpine + Jinja + Plotly.js | **Alpine + Jinja + vendored Plotly** (no HTMX yet) |
| Desktop | pywebview (+ PyInstaller) | pywebview; `--server` browser fallback; **installer not done** |
| Models | Pydantic v2 | Pydantic v2 |
| Persistence | SQLite registry + project folders | **In-memory `Library` + portable project folders** (`project.json` + `.cellpy` under `~/.cellpy_simple_gui/projects/`). No SQLite yet. |
| Background | ProcessPoolExecutor + SSE | **Thread-pool JobManager + SSE** |
| Packaging | PyInstaller + InnoSetup (reuse `cellpy_streamlit_installer`) | **Pending** — next major step |
| Testing | pytest, httpx TestClient, optional Playwright | pytest + httpx TestClient (~34 tests) |

HTMX vs React remains an open upgrade path: keep a clean JSON API so a page can
swap later without touching core.

---

## 4. Package layout

**Design** sketched a uv monorepo (`packages/cellprocessor_{core,api,ui}`,
`apps/desktop`, `apps/cli`).

**MVP** is a single installable package:

```
src/cellpy_simple_gui/
├── core/          # models, library, adapter, collect, plotting, projects, export, files
├── api/           # FastAPI, jobs, routers
├── web/           # templates + static
├── desktop.py
├── server.py
└── __main__.py
```

Do not invent a monorepo split unless an issue explicitly asks for it.

---

## 5. Core layer rules

- **`cellpy_adapter.py`** — load/configure/save surface (`cellpy.get`, example
  data, raw ingest, save). Prefer this for I/O.
- **`collect.py`** — bridge Library → `cellpy.collect.from_cells` →
  `Collection.plot()` / export. This is intentional: science plotting should
  come from cellpy, not a hand-rolled Plotly layer.
- **`library.py`** — in-memory loaded cells = runtime source of truth.
- **`projects.py`** — portable folders: `CellpyCell.save(..., overwrite=True)`
  into `data/<id>.cellpy` + `project.json` for grouping/labels/selection.
- Services return **Plotly figure JSON**, never live figure objects that only
  the UI can consume.

### cellpy 2.1.1 surface to prefer

| Use | Avoid / note |
|---|---|
| `cellpy.collect.from_cells(cells, groups=, selected=, group_labels=)` | Old batch-shim (`_BatchShim`) — removed after upstream #787 |
| `cellpy.list_instruments()` | Hard-coded instrument lists; still suppress loader-probe warnings |
| `Collection.is_grouped` | Sniffing for a `mean` column |
| `CurveOptions(mode=, method=)` | Dropping cycle mode/method controls |
| `cell.data.summary` | Deprecated `get_summary()` |
| `cell.get_cap(cycle=, mode=, method=)` → cols `[capacity, potential]` | Guessing column names |
| `cellpy.plotting.registry.families()` | Inventing plot-family names |

Upstream issues filed while building the MVP: [jepegit/cellpy#785–#791](https://github.com/jepegit/cellpy/issues/785)
(most fixed in 2.1.1). Details: repo `CELLPY_PAINPOINTS.md`.

### Summary DataFrame columns (handy)

- Capacity: `charge_capacity` / `discharge_capacity` (absolute),
  `…_gravimetric` (mAh/g), `…_areal` (mAh/cm²)
- Also: `cycle_num`, `coulombic_efficiency`, `ir_charge` / `ir_discharge`

---

## 6. API sketch (design)

Thin REST + SSE. Routers map to services. Security: bind `127.0.0.1` only;
per-launch token on every request.

MVP routers today: `cells`, `plots`, `export`, `jobs`, `projects`, `ingest`,
`system`. Extend these rather than inventing a parallel API.

Job flow: `POST` work → `{job_id}` → `GET /jobs/{id}/events` (SSE) → optional
cancel. Persist job history was a design goal (SQLite); MVP keeps jobs in-process.

---

## 7. Frontend pages (parity map)

| Streamlit (`cell_processor_app`) | Target / MVP |
|---|---|
| Welcome / Settings / Info | Project picker + settings |
| Raw-file Loader | Ingest wizard (raw → metadata → SSE progress) — **done** |
| Journal Loader | Open project / journal / glob load — **done** |
| Summary Plotter / Collectors | Cycle summary via cellpy collect — **done** |
| Cell Plotter | Cell explorer (cycles collect) — **done** |
| Packaging / first-run | **Not done** |

---

## 8. Packaging, native deps & updates (still open)

From the design doc — treat as the packaging epic checklist:

- PyInstaller one-folder from `desktop` entry → InnoSetup installer (patterns in
  sibling `cellpy_streamlit_installer`).
- Ensure WebView2 on target Windows.
- Arbin `.res`: MVP already loads via Access ODBC on Windows; prefer that path
  over bundling mdbtools unless another instrument needs it.
- Ship wheels via uv — no MSVC Build Tools on target machines.
- Optional update check against GitHub Releases (config-gated for offline labs).

---

## 9. Phased roadmap

| Phase | Intent | MVP status |
|---|---|---|
| 0. Scaffold | uv project, FastAPI + pywebview hello | **Done** |
| 1. Core + cellpy 2.1 | Adapter, load journal/cells → summary JSON | **Done** (library + collect) |
| 2. Ingest + jobs | Raw → cellpy with SSE progress/cancel | **Done** |
| 3. UI parity | Ingest, journal, summary/cell, export | **Mostly done** |
| 4. Packaging | PyInstaller + InnoSetup + WebView2 | **Next** |
| 5. Polish | Update check, diagnostics, v1/batbase import, docs | Open |

Design MVP exit was phases 0–2; shipping to lab users needs phase 4.

---

## 10. Risks & open questions

- cellpy API drift — keep adapter/collect thin; pin behaviour with tests.
- Plotly.js vs kaleido export parity (fonts/sizing).
- pywebview + WebView2 on clean Windows machines.
- Whether to later add SQLite registry / ProcessPool (only if threads or
  in-memory library prove insufficient — don't add "because the design said so").
- CLI as first-class deliverable vs internal smoke harness.

---

## 11. Sibling repos (context only)

| Repo | Role |
|---|---|
| `cellpy-simple-gui` | **This app** — active development |
| `cell_processor_app` | Legacy Streamlit demo (cellpy v1 era) — reference, not the target |
| `cellpy_streamlit_installer` | Existing InnoSetup/uv packaging know-how to reuse for phase 4 |

When packaging work starts, read the installer repo before inventing a new
pipeline. Lifecycle issue tracking for the new app stays in **this** repo's
`.issueflows/`.
