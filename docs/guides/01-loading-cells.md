# 1. Getting cells into memory

*You have files. You want `CellpyCell` objects.*

Everything on this page goes through one function. That is the good news, and it
is genuinely one of the nicest things about the library: there is no loader class
to pick, no reader to construct, no session to open.

```python
import warnings

import cellpy
from cellpy.utils import example_data

warnings.simplefilter("ignore")  # the demo files are old enough to grumble

cell = example_data.cellpy_file()
print(type(cell).__name__, cell.cell_name, len(cell.get_cycle_numbers()), "cycles")
```

```text
CellpyCell 20180418_sf033_4_cc 304 cycles
```

`example_data` downloads once into `~/cellpy_data/examples` and caches, which
makes a zero-setup demo trivial — worth wiring into any app you build, because
"press this to see it work" beats a file dialog on first run.

## Opening a real file

```python
import cellpy
from cellpy.utils import example_data

path = example_data.neware_file_path()   # a real Neware export — note: .csv

# Only the filename is required; the rest is metadata cellpy cannot get
# from the file.
cell = cellpy.get(
    filename=path,
    instrument="neware_txt",
    mass="0.47 mg",              # unit strings are accepted, and are clearer
    area="1.77 cm**2",
    nominal_capacity="372 mAh/g",
)
print(path.name, "·", len(cell.get_cycle_numbers()), "cycles ·", round(cell.mass, 3), "mg")
```

```text
neware_uio.csv · 4 cycles · 0.47 mg
```

Two things about that call are worth internalising.

**Units can be strings.** `mass="0.47 mg"` beats `mass=0.47` plus a comment, and
cellpy parses it. Wherever an argument is a physical quantity, try the string.

**`mass` is not cosmetic.** Every `*_gravimetric` column in the summary is
computed against it — and if you omit it, the columns are still there:

```python
no_mass = cellpy.get(filename=path, instrument="neware_txt")
print("mass:", no_mass.mass)
print("first discharge, per gram:", round(
    no_mass.data.summary["discharge_capacity_gravimetric"].iloc[0], 1))
print("with the real mass:      ", round(
    cell.data.summary["discharge_capacity_gravimetric"].iloc[0], 1))
```

```text
mass: 1.0
first discharge, per gram: 5086.3
with the real mass:       2390.1
```

Nothing failed. The mass silently defaulted to 1.0 mg, and you get a chart with
correct-looking axes and numbers that are wrong by a factor of the real mass. If
your app takes files from users, ask for mass at ingestion time, not later.

## Which instrument?

`instrument=` is a string, and the list is discovered at runtime rather than
hard-coded, so it depends on the installed cellpy:

```python
import cellpy

instruments = cellpy.list_instruments()
print(len(instruments), "loaders")
print(instruments[0])
```

```text
13 loaders
{'id': 'arbin_res', 'label': 'Arbin (res)', 'models': ['default'], 'suffixes': ['.res']}
```

`suffixes` is what you want for a file-dialog filter; `models` is a
sub-selection some instruments offer (the literal `"default"` entry means "no
model chosen", so drop it before showing the list to anyone).

You can also let cellpy pick from the suffix by leaving `instrument` out. Do that
for convenience, not for correctness — the Neware file above is a `.csv`, and so
are the PEC and custom-format examples.

> **`.h5` is special.** A set `instrument=` wins over the `.h5` / `.hdf5` suffix,
> so you can load an HDF5 file that is *not* a cellpy file by naming its loader.
> That was not always true ([cellpy#819](https://github.com/jepegit/cellpy/issues/819),
> fixed in 2.1.2a2) — before it, `auto_pick_cellpy_format=False` was required, and
> code that still passes it can drop it.

## Discovered is not the same as usable

This is the trap on this page, and it cost a full build cycle to notice.

`list_instruments()` reports what cellpy *registers*, not what this machine can
actually read. Arbin `.res` is a Microsoft Access database, so it needs a reader
that is nobody's default install: `mdbtools` (providing the `mdb-export` binary)
on Linux and macOS, or the Access Database Engine on Windows. Without it, loading
does not raise something helpful:

```pycon
>>> cellpy.get(filename="cell.res", instrument="arbin_res")
FileNotFoundError: [Errno 2] No such file or directory: 'mdb-export'
```

Worse, in a batch import the failure can be a per-file error inside a result
rather than an exception. Our smoke test asserted the import job reached
`status: "done"`. It did — and imported zero cells, for a whole build cycle,
because the failure lived in the payload:

```json
{"added": [], "errors": ["Arbin demo (.res): [Errno 2] No such file or directory: 'mdb-export'"]}
```

Two things follow. **Probe before you offer**, so the UI can grey an entry out
rather than let someone pick a file and wait to find out:

```python
import shutil
import sys


def arbin_res_readable() -> bool:
    """Can this machine read an Arbin .res? Never raises — no opinion is 'yes'."""
    try:
        if sys.platform != "win32":
            return shutil.which("mdb-export") is not None
        import pyodbc

        return any("microsoft access driver" in d.lower() for d in pyodbc.drivers())
    except Exception:  # noqa: BLE001 - an inconclusive probe must not hide a working loader
        return True


print("arbin .res readable here:", arbin_res_readable())
```

And **translate the error**, because "mdb-export" tells a battery researcher
nothing:

```python
_ENVIRONMENT_ERRORS = (
    (("im002", "odbc driver manager", "no default driver"),
     "Reading Arbin .res needs the Microsoft Access Database Engine (64-bit), "
     "a free Microsoft download."),
    (("mdb-export",),
     "Reading Arbin .res on Linux/macOS needs mdbtools, which provides "
     "`mdb-export`. Debian/Ubuntu: apt install mdbtools"),
)


def explain(exc: BaseException) -> str:
    """Anything unrecognised passes through: a wrong explanation is worse."""
    text = str(exc).lower()
    for signatures, explanation in _ENVIRONMENT_ERRORS:
        if any(s in text for s in signatures):
            return explanation
    return str(exc)


print(explain(FileNotFoundError("[Errno 2] ... 'mdb-export'")))
```

A related quiet failure: `arbin_sql` and `arbin_sql_7` raise `ImportError` during
discovery when `libodbc.so.2` is absent, so the list comes back with 11 entries
instead of 13 and nothing says why. If your instrument count matters, assert on
it. *(Both raised as [cellpy#938](https://github.com/jepegit/cellpy/issues/938).)*

## Looking before you load

Loading a large `.res` takes real time, so for a file picker or an import preview
you usually want the metadata without the data:

```python
import cellpy
from cellpy.utils import example_data

meta = cellpy.read_meta(example_data.cellpy_file_path())
print(sorted(meta)[:6])
print("mass:", meta["cell"]["mass"])
```

```text
['active_test_id', 'cell', 'cellpy_file_version', 'cellpy_units', 'cycle_schema_version', 'frames_had_test_id']
mass: 0.28898447708417657
```

**`read_meta` reads cellpy files only.** It goes straight to the HDF5 reader
whatever the suffix, so handing it a raw `.res` produces an HDF5 superblock
traceback rather than "that is not a cellpy file". Guard it on your side:

```python
from pathlib import Path

CELLPY_SUFFIXES = {".cellpy", ".h5", ".hdf5"}


def peek(path) -> dict | None:
    path = Path(path)
    if path.suffix.lower() not in CELLPY_SUFFIXES:
        return None          # raw file: there is no cheap read, load it properly
    return cellpy.read_meta(path)


print(peek(example_data.arbin_file_path()))
```

## Asking the user for the right metadata

Different instruments need different things, and hard-coding a form per
instrument ages badly. cellpy will describe the fields for you:

```python
import cellpy

schema = cellpy.instrument_meta_schema("arbin_res")
for field in schema["fields"][:3]:
    print(f"{field['name']:<8} required={field['required']!s:<5} unit={field['unit']}")
```

```text
mass     required=True  unit=mg
area     required=False unit=cm**2
loading  required=False unit=mg/cm**2
```

Each field carries `name`, `required`, `type`, `unit`, `default`, `maps_to` and
`help` — enough to generate an ingestion form rather than maintain one.

## Many files at once

There is no batch-load call: loop, and decide your own failure policy. The policy
matters more than the loop.

```python
def load_many(paths, **kwargs):
    """One bad file should not lose the other nine."""
    cells, errors = {}, []
    for path in paths:
        try:
            cells[Path(path).stem] = cellpy.get(filename=path, **kwargs)
        except Exception as exc:  # noqa: BLE001 - report it, keep going
            errors.append(f"{Path(path).name}: {explain(exc)}")
    return cells, errors


cells, errors = load_many(
    [example_data.cellpy_file_path(), "/definitely/not/here.res"]
)
print(len(cells), "loaded ·", errors)
```

If you expand globs, **cap the expansion**. A stray `*` in a directory of
archives will otherwise pull in a few hundred files and look like a hang; a low
default with a clear "showing the first N" message is kinder than an honest but
unbounded loop.

## Where to go next

Cells in a dict, keyed by a name you chose, is exactly the shape
[guide 2](02-collections.md) starts from.

---

*Sources: `cellpy.get`, `cellpy.list_instruments`, `cellpy.read_meta`,
`cellpy.instrument_meta_schema`, `cellpy.utils.example_data`. Traps from
[CELLPY_PAINPOINTS.md](../../CELLPY_PAINPOINTS.md) §31 and
[cellpy-simple-gui#143](https://github.com/cellpy/cellpy-simple-gui/issues/143).*
