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
import warnings
from pathlib import Path
from typing import Any

import pandas as pd

log = logging.getLogger(__name__)

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

    return {
        "name": str(getattr(cell, "cell_name", "") or ""),
        "mass": _num(getattr(cell, "mass", None)),
        "area": _num(getattr(cell, "active_electrode_area", None)),
        "nominal_capacity": _num(getattr(cell, "nominal_capacity", None)),
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


def save_cell(cell: Any, path: str | Path) -> None:
    """Write a cell to a self-contained ``.cellpy`` file (overwriting)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        cell.save(str(path), overwrite=True)


def set_mass(cell: Any, mass: float) -> None:
    """Update the active-material mass and refresh the summary."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        cell.mass = mass
        try:
            cell.make_summary()
        except Exception:  # noqa: BLE001
            log.warning("Could not remake summary after mass change", exc_info=True)


def cellpy_version() -> str:
    import cellpy

    return str(cellpy.__version__)
