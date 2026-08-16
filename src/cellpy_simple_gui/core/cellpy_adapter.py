"""The one and only bridge to cellpy (>= 2.1).

Every cellpy import and every cellpy call in the whole application lives here.
The rest of the code speaks in plain dicts / DataFrames / our own models, so a
cellpy API change is contained to this file.

API pinned against cellpy 2.1:
    * ``cellpy.get(filename=..., mass=...)``            -> CellpyCell
    * ``cell.data.summary``                             -> summary DataFrame
    * ``cell.get_cap(cycle=, mode=, method=)``          -> DataFrame[potential, capacity]
    * ``cell.get_cycle_numbers()``                      -> cycle numbers
    * ``cell.cell_name / mass / active_electrode_area / nominal_capacity``
    * ``cellpy.utils.example_data``                     -> bundled demo cells
"""

from __future__ import annotations

import logging
import sys
import warnings
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd

log = logging.getLogger(__name__)

# Optional ``(fraction, message)`` hook for long cellpy calls (jobs / UI).
ProgressFn = Callable[[float, str], None] | None

# cellpy is imported lazily inside functions so that importing this module (and
# therefore running fast unit tests / the API import) does not pay the cellpy
# import cost until a cell is actually loaded.


# --------------------------------------------------------------------------- #
# Example / demo data
# --------------------------------------------------------------------------- #

#: Built-in demo cells. Keys are stable ids used by the API/UI.
EXAMPLE_CELLS: dict[str, dict[str, str]] = {
    "cellpy": {
        "label": "Si/C anode (sf033)",
        "description": "Silicon-carbon half-cell, 300+ cycles.",
    },
    "old_cellpy": {
        "label": "Legacy test cell",
        "description": "Older cellpy-format example cell.",
    },
    "rate": {
        "label": "Rate-capability cell",
        "description": "Cell cycled at varying C-rates.",
    },
}


def load_example(kind: str) -> Any:
    """Load one bundled example cell. Returns a ``CellpyCell``.

    ``kind`` is one of :data:`EXAMPLE_CELLS`.
    """
    from cellpy.utils import example_data

    kind = kind.lower()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if kind == "cellpy":
            return example_data.cellpy_file()
        if kind == "old_cellpy":
            path = example_data.old_cellpy_file_path()
        elif kind == "rate":
            path = example_data.rate_file()
        else:
            raise ValueError(f"Unknown example cell: {kind!r}")
        return _get(filename=path)


_INSTRUMENTS_CACHE: list[dict[str, Any]] | None = None


def list_instruments() -> list[dict[str, Any]]:
    """The available instrument loaders (id / label / models / suffixes).

    Uses cellpy's :func:`cellpy.list_instruments` (quiet by contract since
    2.1.1.post3 / #786). Drops the implicit ``"default"`` pseudo-model (the UI
    treats "no model selected" as default).
    """
    global _INSTRUMENTS_CACHE
    if _INSTRUMENTS_CACHE is not None:
        return _INSTRUMENTS_CACHE

    import cellpy

    try:
        raw = cellpy.list_instruments()
    except Exception:  # noqa: BLE001 - never let discovery break the app
        log.warning("Could not discover cellpy instruments", exc_info=True)
        raw = []

    instruments: list[dict[str, Any]] = []
    for entry in raw:
        models = [m for m in entry.get("models", []) if m != "default"]
        instruments.append(
            {
                "id": entry["id"],
                "label": entry.get("label") or entry["id"],
                "models": models,
                "suffixes": entry.get("suffixes", []),
                # Discovered *and* usable are different questions. arbin_res is
                # listed on any machine but only works where a reader for
                # Access databases exists, so the UI is told which it is rather
                # than letting someone pick a file and wait to find out (#143).
                "available": True,
                "unavailable_reason": None,
            }
        )

    if not arbin_res_reader_available():
        for entry in instruments:
            if entry["id"] == "arbin_res":
                entry["available"] = False
                entry["unavailable_reason"] = _ARBIN_RES_HINT

    instruments.sort(key=lambda i: i["id"])
    _INSTRUMENTS_CACHE = instruments
    return instruments


def instrument_ids() -> set[str]:
    return {i["id"] for i in list_instruments()}


#: Environmental failures that are about the *machine*, not the file, and whose
#: raw text tells a battery researcher nothing. Each maps a signature to an
#: explanation naming the cause and the fix.
#:
#: Both entries are for Arbin `.res`, which is an Access database and therefore
#: needs a platform-specific reader that is nobody's default install:
#:
#:   Windows — the Access ODBC driver, which arrives with Office or with
#:             Microsoft's free Access Database Engine redistributable.
#:   posix   — mdbtools, which provides the `mdb-export` binary cellpy shells
#:             out to.
#:
#: Both were found by running the app on a machine that lacked them (a CI
#: runner, and the container), never by reading the code (#143, #121).
_ENVIRONMENT_ERRORS: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        ("im002", "odbc driver manager", "no default driver"),
        "Reading Arbin .res needs the Microsoft Access Database Engine "
        "(64-bit), a free Microsoft download — it is not installed on this "
        "machine. Every other format works without it. "
        "https://www.microsoft.com/en-us/download/details.aspx?id=54920",
    ),
    (
        ("mdb-export",),
        "Reading Arbin .res on Linux/macOS needs mdbtools, which provides "
        "`mdb-export` — it is not installed on this machine. "
        "Debian/Ubuntu: apt install mdbtools · macOS: brew install mdbtools",
    ),
)


#: Loaders that need something the machine may not have, and how to tell.
#: Only Arbin `.res` so far — the SQL loaders need a server rather than a local
#: reader, which is a different kind of "unavailable" and not ours to probe.
_ARBIN_RES_HINT = (
    "Needs the Microsoft Access Database Engine (64-bit), a free Microsoft "
    "download."
    if sys.platform == "win32"
    else "Needs mdbtools (provides `mdb-export`)."
)


def arbin_res_reader_available() -> bool:
    """Can this machine actually read an Arbin ``.res``?

    Cheap enough to call on every instrument listing: a ``shutil.which`` on
    posix, and on Windows a driver enumeration that does not open a connection.
    Never raises — an inconclusive probe reports *available*, so a bad guess
    cannot hide a loader that would have worked.

    The guard covers *both* branches, which the first version did not: only the
    Windows one was wrapped, so on posix an unhappy ``shutil.which`` would have
    propagated out of a listing and broken the instrument picker. Untestable
    from a Windows box — the posix branch is dead code there — and duly caught
    by the Linux CI the first time it ran.
    """
    try:
        if sys.platform != "win32":
            import shutil

            return shutil.which("mdb-export") is not None

        import pyodbc

        return any("microsoft access driver" in d.lower() for d in pyodbc.drivers())
    except Exception:  # noqa: BLE001 - no reader, no driver manager, no opinion
        return True


def explain_load_error(exc: BaseException) -> str:
    """Turn a loader failure into something a user can act on (#143).

    A raw ``pyodbc.InterfaceError`` reaching a toast names neither the problem
    nor the fix, and the reader it is complaining about is not something most
    people know they are missing. Anything unrecognised is passed through
    unchanged — a wrong explanation would be worse than a raw one.
    """
    text = str(exc).lower()
    for signatures, explanation in _ENVIRONMENT_ERRORS:
        if any(s in text for s in signatures):
            return explanation
    return str(exc)


def instrument_meta_schema(instrument: str | None = None) -> dict[str, Any]:
    """Describe ``cellpy.get`` metadata knobs for an ingestion form (#800)."""
    import cellpy

    return cellpy.instrument_meta_schema(instrument)


def read_file_meta(path: str | Path) -> Any:
    """Peek cellpy-file metadata without loading raw/steps/summary (#799)."""
    import cellpy

    return cellpy.read_meta(path)

#: Bundled raw files that "Import raw demo" can pull in with zero setup.
EXAMPLE_RAW = {
    "neware": {"instrument": "neware_txt", "model": None, "label": "Neware demo (.csv)"},
    "pec": {"instrument": "pec_csv", "model": None, "label": "PEC demo (.csv)"},
    "maccor": {"instrument": "maccor_txt", "model": "three", "label": "Maccor demo (.txt)"},
    "arbin": {"instrument": "arbin_res", "model": None, "label": "Arbin demo (.res)"},
}


def load_raw(
    path: str | Path,
    instrument: str,
    *,
    model: str | None = None,
    mass: float | None = None,
    area: float | None = None,
    nominal_capacity: float | None = None,
    nom_cap_specifics: str | None = None,
    cycle_mode: str | None = None,
) -> Any:
    """Load and process a raw instrument file into a ``CellpyCell``.

    Only the metadata the caller actually supplied is passed through, so cellpy
    falls back to its own defaults for anything left blank.

    A set ``instrument=`` now wins over ``.h5`` / ``.hdf5`` suffix auto-pick in
    cellpy ≥2.1.2 (#819), so raw HDF5 loaders (e.g. Arbin SQL HDF5) route to the
    right reader without disabling ``auto_pick_cellpy_format``.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"No such file: {p}")
    kwargs: dict[str, Any] = {
        "filename": str(p),
        "instrument": instrument,
    }
    if model:
        kwargs["model"] = model
    if mass:
        kwargs["mass"] = mass
    if area:
        kwargs["area"] = area
    if nominal_capacity:
        kwargs["nominal_capacity"] = nominal_capacity
    if nom_cap_specifics:
        kwargs["nom_cap_specifics"] = nom_cap_specifics
    if cycle_mode:
        kwargs["cycle_mode"] = cycle_mode
    try:
        return _get(**kwargs)
    except Exception as exc:  # noqa: BLE001 - rephrase loader mismatch only
        rewritten = _rewrite_loader_error(exc, path=p, instrument=instrument)
        if rewritten is exc:
            raise
        raise rewritten from exc


def _rewrite_loader_error(exc: Exception, *, path: Path, instrument: str) -> Exception:
    """Hint when the cellpy-native HDF5 reader ran instead of a raw loader."""
    if "data_df" not in str(exc):
        return exc
    return RuntimeError(
        f"{path}: cellpy tried its native HDF5 reader (looking for 'data_df') "
        f"instead of instrument {instrument!r}. For Arbin SQL HDF5 use Import raw "
        f"with Instrument = Arbin SQL (HDF5) (id arbin_sql_h5); Load cells is only "
        f"for native cellpy .cellpy/.h5 files. Original error: {exc}"
    )


def example_raw_path(kind: str) -> Path:
    """Return the path to a bundled example raw file (downloading if needed)."""
    from cellpy.utils import example_data

    kind = kind.lower()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if kind == "neware":
            return example_data.neware_file_path()
        if kind == "pec":
            return example_data.pec_file_path()
        if kind == "maccor":
            return example_data.maccor_file_path_type_three()
        if kind == "arbin":
            return example_data.arbin_file_path()
    raise ValueError(f"Unknown raw example: {kind!r}")


def load_file(path: str | Path, mass: float | None = None) -> Any:
    """Load a cellpy file (``.cellpy`` / legacy ``.h5``) from disk."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"No such file: {p}")
    kwargs: dict[str, Any] = {"filename": str(p)}
    if mass is not None:
        kwargs["mass"] = mass
    return _get(**kwargs)


def _get(**kwargs: Any) -> Any:
    import cellpy

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return cellpy.get(**kwargs)


# --------------------------------------------------------------------------- #
# Metadata & data extraction (cellpy -> plain python)
# --------------------------------------------------------------------------- #


def read_meta(cell: Any) -> dict[str, Any]:
    """Return a plain-dict projection of a cell's metadata."""

    def _safe(fn, default=None):
        try:
            return fn()
        except Exception:  # noqa: BLE001 - metadata is best-effort
            return default

    def _num(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    mode = getattr(cell, "cycle_mode", None)
    mode_s = str(mode).strip() if mode not in (None, "") else None
    if mode_s not in ("anode", "cathode", "full_cell"):
        mode_s = None

    specs = getattr(cell, "nom_cap_specifics", None)
    specs_s = str(specs).strip() if specs not in (None, "") else None
    if specs_s not in ("gravimetric", "areal", "absolute"):
        specs_s = None

    return {
        "name": str(getattr(cell, "cell_name", "") or ""),
        "mass": _num(getattr(cell, "mass", None)),
        "area": _num(getattr(cell, "active_electrode_area", None)),
        "nominal_capacity": _num(getattr(cell, "nominal_capacity", None)),
        "nom_cap_specifics": specs_s,
        "cycle_mode": mode_s,
        "n_cycles": int(_safe(cell.get_number_of_cycles, 0) or 0),
    }


def summary_frame(cell: Any) -> pd.DataFrame:
    """Return the per-cycle summary DataFrame for a cell.

    Uses the modern ``cell.data.summary`` accessor (``get_summary`` is
    deprecated in 2.1). Guarantees a ``cycle_num`` column.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        summary = cell.data.summary
    df = summary.copy()
    if "cycle_num" not in df.columns:
        # fall back to the index if the column name ever changes
        df = df.reset_index().rename(columns={df.index.name or "index": "cycle_num"})
    return df


def cycle_numbers(cell: Any) -> list[int]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return [int(c) for c in cell.get_cycle_numbers()]


def capacity_curve(
    cell: Any,
    cycle: int,
    mode: str = "gravimetric",
    method: str = "forth-and-forth",
) -> pd.DataFrame:
    """Return a voltage-capacity curve for one cycle.

    Columns: ``capacity``, ``potential``.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        df = cell.get_cap(cycle=cycle, method=method, mode=mode)
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=["capacity", "potential"])
    return df[["capacity", "potential"]].reset_index(drop=True)


def load_journal_cells(
    path: str | Path,
    progress: ProgressFn = None,
) -> list[tuple[str, Any, int]]:
    """Load a cellpy batch journal (.json) and return ``(label, cell, group)``.

    Uses cellpy 2.1's ``batch.from_journal`` + ``batch.load()``. Loads
    **cellpy files only** (not raw instrument paths) so old journals with
    dead lab-share ``raw_file_names`` do not hang forever. Raises if the
    journal can't be parsed; returns an empty list if nothing linkable.
    """
    from cellpy.batch import from_journal
    from cellpy.batch.journal import FILENAME
    from cellpy.batch.policy import LoadPolicy, SourcePreference, resolve_specs
    from cellpy.batch.result import BatchResult
    from cellpy.batch.runner import load_cell
    from cellpy.batch.store import CellStore

    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"No such journal file: {p}")

    def _progress(fraction: float, message: str) -> None:
        if progress is not None:
            progress(fraction, message)

    log.info("Journal: parsing %s", p)
    _progress(0.05, f"Parsing journal {p.name} (from_journal) …")
    policy = LoadPolicy(source=SourcePreference.CELLPY_ONLY, accept_errors=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            batch = from_journal(str(p), policy=policy)
        except Exception as exc:  # noqa: BLE001 - rephrase for the UI
            raise RuntimeError(
                f"Could not parse batch journal “{p.name}”: {exc}"
            ) from exc
        n_pages = 0
        try:
            n_pages = len(batch.journal.pages)
        except Exception:  # noqa: BLE001
            pass
        log.info(
            "Journal: parsed “%s” (%d page row(s)); loading cellpy files only …",
            p.name,
            n_pages,
        )
        _progress(
            0.1,
            f"Loading .cellpy files for {p.name} (batch.load, {n_pages} cell(s)) …",
        )

        # Serial load with *pre*-cell logging. cellpy's on_progress only fires
        # after each cell finishes, so a hang would look silent; we drive
        # load_cell ourselves (same as executor="serial") and log before/after.
        load_exc: Exception | None = None
        try:
            specs = resolve_specs(batch.journal, policy)
            results = []
            total = max(len(specs), 1)
            for i, spec in enumerate(specs, start=1):
                cpath = str(spec.cellpy_file or "(no cellpy path)")
                log.info(
                    "Journal: loading %d/%d “%s” ← %s …",
                    i,
                    len(specs),
                    spec.label,
                    cpath,
                )
                _progress(
                    0.1 + 0.7 * ((i - 1) / total),
                    f"Loading cell {i}/{len(specs)}: “{spec.label}” …",
                )
                result = load_cell(spec, policy)
                results.append(result)
                outcome = getattr(result.outcome, "value", result.outcome)
                err = f" — {result.error}" if result.error else ""
                log.info(
                    "Journal: loaded %d/%d “%s” → %s (%.1fs)%s",
                    i,
                    len(specs),
                    spec.label,
                    outcome,
                    result.seconds,
                    err,
                )
                _progress(
                    0.1 + 0.7 * (i / total),
                    f"Loaded cell {i}/{len(specs)}: “{spec.label}” ({outcome}) …",
                )
            batch._result = BatchResult(results)
            batch._store = CellStore.from_cells(batch._result.cells())
            batch._summaries = None
        except Exception as exc:  # noqa: BLE001 - may still have partial cells
            # Job cancel propagates via the progress callback — don't swallow it.
            if type(exc).__name__ == "Cancelled":
                raise
            load_exc = exc
            log.warning("Journal cell load failed for %s", p, exc_info=True)
        else:
            log.info("Journal: cell load finished for “%s”", p.name)

    groups: dict[str, int] = {}
    try:
        pages = batch.journal.pages
        cols = pages.columns
        if FILENAME in cols and "group" in cols:
            for row in pages.iter_rows(named=True):
                groups[row[FILENAME]] = int(row.get("group") or 1)
    except Exception:  # noqa: BLE001 - group metadata is best-effort
        pass

    n_keys = 0
    try:
        n_keys = len(batch.cells)
    except Exception:  # noqa: BLE001
        pass
    log.info("Journal: probing %d batch cell key(s) for usable data …", n_keys)
    _progress(0.85, f"Checking {n_keys} loaded cell(s) …")

    out: list[tuple[str, Any, int]] = []
    skipped = 0
    for label, cell in batch.cells.items():
        if cell is None:
            skipped += 1
            continue
        # Skip shells the journal referenced but whose .cellpy file couldn't be
        # loaded — touching the data raises for those.
        try:
            cell.get_number_of_cycles()
        except Exception:  # noqa: BLE001
            skipped += 1
            continue
        out.append((str(label), cell, groups.get(str(label), 1)))

    log.info(
        "Journal: %d linkable cell(s), %d skipped/empty (from “%s”)",
        len(out),
        skipped,
        p.name,
    )
    if not out and load_exc is not None:
        raise RuntimeError(
            f"Could not load cells from journal “{p.name}”: {load_exc}"
        ) from load_exc
    return out


def save_cell(cell: Any, path: str | Path) -> None:
    """Write a cell to a self-contained ``.cellpy`` file (overwriting)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        cell.save(str(path), overwrite=True)


def export_cell_excel(cell: Any, path: str | Path) -> None:
    """Write a cell via cellpy ``to_excel`` (default sheets / options)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        cell.to_excel(str(path))


def export_cell_csv(cell: Any, datadir: str | Path) -> list[Path]:
    """Write cellpy ``to_csv`` outputs into ``datadir``; return created files."""
    dest = Path(datadir)
    dest.mkdir(parents=True, exist_ok=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        cell.to_csv(datadir=str(dest))
    return sorted(p for p in dest.rglob("*") if p.is_file())


def _remake_summary(cell: Any, changed: list[str]) -> None:
    """Refresh the summary after a physical meta change.

    cellpy ≥2.1.2a4 exposes ``refresh_after`` (#846), which recomputes only the
    meta-dependent (scaled / equivalent-cycle) columns instead of rebuilding the
    whole cycle-end table. It falls back to ``make_summary`` itself when there is
    no summary yet, so this is a straight upgrade over the old full rebuild.
    """
    what = "+".join(changed)
    refresh = getattr(cell, "refresh_after", None)
    try:
        if callable(refresh):
            refresh(fields=changed)
        else:  # cellpy < 2.1.2a4
            cell.make_summary()
    except Exception:  # noqa: BLE001
        log.warning("Could not refresh summary after %s change", what, exc_info=True)


def apply_physical_meta(
    cell: Any,
    *,
    mass: float | None = None,
    area: float | None = None,
    nominal_capacity: float | None = None,
    nom_cap_specifics: str | None = None,
    cycle_mode: str | None = None,
) -> list[str]:
    """Assign physical meta knobs and refresh the summary once.

    Returns the names of fields that were applied. The refresh is selective as
    of cellpy 2.1.2a4 (#846) — see :func:`_remake_summary`.
    """
    changed: list[str] = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if mass is not None and mass > 0:
            cell.mass = mass
            changed.append("mass")
        if area is not None and area > 0:
            cell.active_electrode_area = area
            changed.append("area")
        if nominal_capacity is not None and nominal_capacity > 0:
            cell.nominal_capacity = nominal_capacity
            changed.append("nominal_capacity")
        if nom_cap_specifics is not None:
            cell.nom_cap_specifics = nom_cap_specifics
            changed.append("nom_cap_specifics")
        if cycle_mode is not None:
            cell.cycle_mode = cycle_mode
            changed.append("cycle_mode")
        if changed:
            _remake_summary(cell, changed)
    return changed


def set_mass(cell: Any, mass: float) -> None:
    """Update the active-material mass and refresh the summary."""
    apply_physical_meta(cell, mass=mass)


def set_area(cell: Any, area: float) -> None:
    """Update active electrode area (cm²) and refresh the summary."""
    apply_physical_meta(cell, area=area)


def set_nominal_capacity(cell: Any, nominal_capacity: float) -> None:
    """Update nominal capacity and refresh the summary."""
    apply_physical_meta(cell, nominal_capacity=nominal_capacity)


def set_nom_cap_specifics(cell: Any, nom_cap_specifics: str) -> None:
    """Update nominal-capacity basis and refresh the summary."""
    apply_physical_meta(cell, nom_cap_specifics=nom_cap_specifics)


def set_cycle_mode(cell: Any, cycle_mode: str) -> None:
    """Update cycle mode (anode/cathode/full_cell) and refresh the summary."""
    apply_physical_meta(cell, cycle_mode=cycle_mode)


def cellpy_version() -> str:
    import cellpy

    return str(cellpy.__version__)
