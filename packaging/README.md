# Packaging

Build a frozen Windows app and prove it actually works.

```bash
uv sync --extra build
uv run pyinstaller packaging/cellpy-simple-gui.spec --noconfirm
uv run python packaging/smoke_test.py dist/cellpy-simple-gui/cellpy-simple-gui.exe
```

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

## Notes for the installer (#122)

- `console=True` here is deliberate for diagnosis. Flipping it for the shipped
  app hides startup failures; pair it with a log file or a crash dialog.
- Nothing in the app needed changing to be frozen. `api/deps.py` resolves
  `WEB_DIR` as `Path(__file__).parent.parent / "web"`, which keeps working
  because the spec places the web assets at `cellpy_simple_gui/web` inside the
  bundle. Keep those two in step.
- `pywebview` is still bundled here. Once it moves to a `[desktop]` extra
  (#118), the frozen build must explicitly opt in — a server-only bundle would
  otherwise silently lose the native window.
