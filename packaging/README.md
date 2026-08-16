# Packaging

Two shipping routes: a frozen Windows app (#117, #122) and a server container
(#121). Both are proved the same way — by driving what ships over HTTP.

```bash
# frozen Windows app
uv sync --extra build --extra desktop --extra export
uv run pyinstaller packaging/cellpy-simple-gui.spec --noconfirm
uv run python packaging/smoke_test.py dist/cellpy-simple-gui/cellpy-simple-gui.exe

# container
docker build -t cellpy-simple-gui .
docker run -d --name csg -p 127.0.0.1:8577:8577 -e CSG_TOKEN=t -v csg-data:/data cellpy-simple-gui
uv run python packaging/smoke_test.py --url http://127.0.0.1:8577 --token t
```

`--extra desktop` is not optional for a shipped build: since #118 the native
window is an extra, and PyInstaller can only bundle what is installed. Leave it
out and you get a working app that silently only ever opens a browser.

The smoke test drives the **built binary over HTTP** rather than importing
anything, because the failures worth catching here only exist in the frozen
form. It exits non-zero on the first failure, so it can gate a release (#124).

## What the spike established (#117)

**The .exe route is viable.** All 9 smoke checks pass against the frozen build:
13 of 13 instrument loaders discovered, a real Arbin `.res` and a Maccor text
file both imported, summary and dQ/dV figures rendered, CSV exported.

**`collect_all("cellpy")` is load-bearing, and that is measured rather than
assumed.** Building the same spec with only that removed produces an app that
does not start:

```
ModuleNotFoundError: No module named 'cellpy.readers.filefinder'
  ... cellpy/__init__.py line 91, in __getattr__
```

cellpy resolves most of its public surface through a module-level `__getattr__`
(PEP 562) backed by `importlib.import_module`, and its instrument loaders
through module names built as strings. Static analysis sees none of it.

Two corrections to what the plan assumed before the spike:

- The problem is **wider** than instrument discovery. It is cellpy's whole
  top-level API, so it bites on import, not on first use.
- The plan predicted a *silent* failure — an app that starts and reports zero
  instruments. In practice it is a hard crash at startup. Louder, and easier to
  catch. But only because this spec sets `console=True`: a windowed build would
  show nothing at all, so the installer build should keep a way to surface
  startup errors.

## Numbers

| | |
|---|---|
| Bundle | **535 MB**, 3957 files (from a 769 MB venv) |
| Startup, warm | **~6.0 s** (4 consecutive runs: 6.5 / 6.0 / 6.3 / 6.2) |
| Startup, very first run | **~62 s** |

The first-run cost is a one-time price for touching ~4000 new files — on
Windows, largely Defender scanning them. It is not the steady state, but a user
installing the app *does* pay it once, and it is long enough that the app looks
hung. Worth either a progress cue or a note in the installer.

~6 s warm is tolerable for a desktop app but not good. Most of it is importing
pandas, polars, pytables and cellpy. If it needs to come down, that is where to
look — not in PyInstaller settings.

## What the container established (#121)

**All 16 smoke checks pass** against the running image, including the ones that
only mean anything when the app is served: the API refuses requests without a
token, the #120 sandbox is active, and a host path outside `/data` is refused by
name. A project saved on the volume survives `docker restart` and reopens with
its cells.

### Two silent failures the first build shipped with

Both were found by *tightening the test*, not by reading the Dockerfile.

**Arbin `.res` imported nothing while the smoke test said PASS.** On posix
cellpy reads `.res` by shelling out to `mdb-export`, which `python:slim` does
not have. The import job still finishes with `status: "done"` — the failure is
only in the result payload:

```json
{"added": [], "errors": ["Arbin demo (.res): [Errno 2] No such file or directory: 'mdb-export'"]}
```

The check asserted on `status` alone, so it passed on an import that imported
nothing. It now asserts on `added` and `errors`. Fixed in the image by
installing `mdbtools`.

**Two loaders vanished from the instrument list.** `arbin_sql` and `arbin_sql_7`
raise `ImportError: libodbc.so.2` during discovery, so they were quietly absent
— 11 instruments instead of 13, with nothing logged at a level anyone would see.
Fixed by installing `unixodbc`. Note that actually connecting to an Arbin SQL
Server still needs a vendor ODBC driver, which is not shipped.

### Server-side figure export is not in the image

Not a size decision. `kaleido>=0.1,<1.4` resolves to **1.3.0**, which does not
bundle a renderer — it drives a separate Chrome via `choreographer`. Measured in
this base image:

- without Chrome: `RuntimeError: Kaleido requires Google Chrome to be installed.`
- after `plotly_get_chrome`, which **exits 0**: `BrowserFailedError — the browser
  seemed to close immediately after starting` (slim lacks Chrome's shared libs)

So a `WITH_EXPORT=1` build arg would have produced a broken image. There isn't
one; [#135](https://github.com/cellpy/cellpy-simple-gui/issues/135) tracks doing
it properly. `core/export.py` now distinguishes "kaleido missing" from "kaleido
present, browser missing", so the 503 stops giving container users advice that
cannot help them.

### Numbers

| | |
|---|---|
| Image, on disk | **1.72 GB** |
| — of which the venv | **1.18 GB** (128 packages) |
| — of which baked demo data | 16 MB |
| — of which `mdbtools` + `unixodbc` | ~10 MB |
| Compressed (what a pull transfers) | **379 MB** |
| Container start to `/healthz` | **~5 s** |

For comparison the Windows venv this is built from is 780 MB; the Linux venv is
larger mostly because `UV_COMPILE_BYTECODE=1` adds `.pyc` for everything, which
is the right trade for a server that starts often.

**Where the weight actually is** — and most of it is not ours:

| package | MB | why it is here |
|---|---|---|
| `_polars_runtime_32` | 206 | polars |
| `pyarrow` | 156 | parquet export |
| `scipy` | 108 | cellpy |
| `pandas` | 72 | core |
| `plotly` | 67 | core |
| `numpy` | 42 | core |
| `matplotlib` | 35 | **`cellpy` — unused by this app, which plots with plotly** |
| `jedi` | 34 | **`cellpy` → `ipykernel` → `ipython` → `jedi`** |
| `debugpy` | 22 | **`cellpy` → `ipykernel` → `debugpy`** |

The last three are ~90 MB of interactive-notebook tooling in a headless server
image, pulled in as *hard* runtime dependencies of cellpy — traced with
`importlib.metadata`, not guessed. Nothing to work around here; it is a
pain-point to raise upstream, and it is filed as one.

## Notes for the installer (#122)

- `console=True` here is deliberate for diagnosis. Flipping it for the shipped
  app hides startup failures; pair it with a log file or a crash dialog.
- Nothing in the app needed changing to be frozen. `api/deps.py` resolves
  `WEB_DIR` as `Path(__file__).parent.parent / "web"`, which keeps working
  because the spec places the web assets at `cellpy_simple_gui/web` inside the
  bundle. Keep those two in step.
- `pywebview` now lives in the `[desktop]` extra (#118), so the build
  environment must include it — see the sync line above. A bundle built without
  it loses the native window and says nothing about it.
