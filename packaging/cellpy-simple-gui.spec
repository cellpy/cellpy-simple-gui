# PyInstaller spec — see .issueflows/05-epics/next-phase-deployment-and-docs.md
#
# The load-bearing part is the cellpy collect_all below. cellpy resolves most of
# its public surface lazily: `cellpy/__init__.py` defines a module-level
# `__getattr__` (PEP 562) that looks names up in `_LAZY_MODULES` / `_LAZY_ATTRS`
# and calls `importlib.import_module`. Instrument loaders are resolved the same
# way, from names built as strings in
# `readers/instruments/configurations/__init__.py`.
#
# None of that is visible to static analysis. Measured, by building this spec
# with the cellpy collect_all removed and changing nothing else: the app does
# not start at all —
#
#     ModuleNotFoundError: No module named 'cellpy.readers.filefinder'
#       ... cellpy/__init__.py line 91, in __getattr__
#
# So this is not an optimisation to trim. Note the failure is only *visible*
# because console=True; a windowed build would simply never appear.
#
# Build (from the repo root):
#   uv run pyinstaller packaging/cellpy-simple-gui.spec --noconfirm
#   uv run python packaging/smoke_test.py dist/cellpy-simple-gui/cellpy-simple-gui.exe

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

ROOT = Path(SPECPATH).parent

datas = []
binaries = []
hiddenimports = []

# --- cellpy and its core ---------------------------------------------------- #
# collect_all pulls submodules *and* package data (instrument config files,
# example-data helpers), which the string-built imports need at runtime.
for pkg in ("cellpy", "cellpycore"):
    _d, _b, _h = collect_all(pkg)
    datas += _d
    binaries += _b
    hiddenimports += _h

# --- things loaded reflectively by their own machinery ---------------------- #
# pytables opens HDF5 through extension modules chosen at runtime.
for pkg in ("tables",):
    _d, _b, _h = collect_all(pkg)
    datas += _d
    binaries += _b
    hiddenimports += _h

# plotly ships package data (templates, validators) it reads on demand.
datas += collect_data_files("plotly")

# uvicorn picks its loop/protocol implementations from strings in config.
hiddenimports += collect_submodules("uvicorn")

# --- the app's own web assets ------------------------------------------------ #
# api/deps.py resolves WEB_DIR as Path(__file__).parent.parent / "web", so the
# bundled copy has to land at cellpy_simple_gui/web for that to keep working
# unchanged inside the bundle.
datas += [(str(ROOT / "src" / "cellpy_simple_gui" / "web"), "cellpy_simple_gui/web")]

a = Analysis(
    [str(ROOT / "packaging" / "entry.py")],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    # Test/build tooling has no business in a shipped app.
    excludes=["pytest", "playwright", "PyInstaller", "IPython", "notebook"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="cellpy-simple-gui",
    debug=False,
    strip=False,
    upx=False,
    # Console for the spike: a frozen app that dies silently is unreviewable.
    # The installer build can flip this once the desktop path is trusted.
    console=True,
    icon=str(ROOT / "src" / "cellpy_simple_gui" / "web" / "static" / "img" / "cellpy-icon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="cellpy-simple-gui",
)
