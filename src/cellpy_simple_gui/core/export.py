"""Data + static-figure export.

Data path: cellpy collections → csv / xlsx / parquet / json.
Figure path: Plotly figure JSON → png / svg / pdf via cellpy's in-memory
``plotting.figures.write_image`` (bytes, no temp files — cellpy #818).
Library cells: cellpy ``save`` / ``to_csv`` / ``to_excel`` → bytes (often zipped).
"""

from __future__ import annotations

import io
import re
import tempfile
import zipfile
from pathlib import Path

import plotly.io as pio
from cellpy.exceptions import OptionalDependencyError
from cellpy.plotting import figures as cellpy_figures

from . import cellpy_adapter, collect, plotting
from .library import CellRecord
from .models import (
    ComparePlotSpec,
    CyclesPlotSpec,
    DvaPlotSpec,
    IcaPlotSpec,
    SummaryPlotSpec,
)

CELL_EXPORT_FORMATS = ("cellpy", "csv", "xlsx")
_CELL_MEDIA = {
    "cellpy": "application/octet-stream",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "zip": "application/zip",
}
_SAFE_STEM = re.compile(r"[^\w.\-]+", re.UNICODE)


_MISSING_KALEIDO = (
    "Static figure export needs kaleido. Install with: uv sync --extra export. "
    "Meanwhile the chart toolbar's camera button still saves a PNG."
)
_MISSING_BROWSER = (
    "Static figure export needs a Chrome or Chromium binary — kaleido is "
    "installed but renders by driving a browser, and none was found. "
    "Meanwhile the chart toolbar's camera button still saves a PNG."
)


class FigureExportError(RuntimeError):
    """Static figure export failed (often missing kaleido or its browser)."""

    def __init__(self, message: str, *, missing_kaleido: bool = False):
        super().__init__(message)
        self.missing_kaleido = missing_kaleido


def summary_export(records: list[CellRecord], spec: SummaryPlotSpec, fmt: str) -> tuple[bytes, str]:
    columns = collect.summary_columns_for(spec.plot_type, spec.basis, records)
    if not columns:
        raise ValueError("This cellpy plot family declares no summary columns.")
    missing = collect.missing_summary_columns(
        collect.summary_required_columns(spec.plot_type, spec.basis, records), records
    )
    if missing:
        raise ValueError("These cells have no " + ", ".join(missing) + ".")
    # cellpy ≥2.1.2 returns one collection that averages multi-member groups
    # while keeping singletons as per-cell rows (#816) — export it directly.
    collection = collect.summary_collection(
        records,
        columns=columns,
        group_it=spec.group_average,
        max_cycle=spec.max_cycle,
        options=collect.summary_options_for(spec.plot_type, records),
        rate=spec.rate,
        rate_on=spec.rate_on,
        rate_std=spec.rate_std,
    )
    if spec.rate is not None and collect.collection_is_empty(collection):
        raise ValueError(collect.no_matching_cycles_message(spec.rate))
    return collect.export_bytes(collection, fmt)


def cycles_export(records: list[CellRecord], spec: CyclesPlotSpec, fmt: str) -> tuple[bytes, str]:
    cycles = tuple(sorted(set(spec.cycles)))
    if spec.curve_kind in ("dqdv", "dvdq"):
        # Export what the chart shows (#95): the differential collection, with
        # the same half-cycle selection the plotter applied.
        collect_fn = (
            collect.ica_collection if spec.curve_kind == "dqdv" else collect.dva_collection
        )
        collection = collect_fn(
            records, cycles=cycles, voltage_resolution=spec.voltage_resolution
        )
        collection = collect.select_ica_direction(collection, spec.direction)
        return collect.export_bytes(collection, fmt)
    collection = collect.cycles_collection(
        records, cycles=cycles, mode=spec.mode, method=spec.method
    )
    return collect.export_bytes(collection, fmt)


def summary_figure_export(
    records: list[CellRecord], spec: SummaryPlotSpec, fmt: str
) -> tuple[bytes, str]:
    if fmt.lower() == "cfz":
        kwargs: dict = {}
        if spec.plot_type.startswith(collect.FAMILY_PREFIX):
            kwargs["y"] = spec.plot_type[len(collect.FAMILY_PREFIX) :]
        return _cells_cfz(records, "summary", kwargs)
    return figure_bytes(plotting.summary_figure(records, spec), fmt)


def cycles_figure_export(
    records: list[CellRecord], spec: CyclesPlotSpec, fmt: str
) -> tuple[bytes, str]:
    if fmt.lower() == "cfz":
        if not spec.cycles:
            raise FigureExportError("Pick one or more cycles to export.")
        kind = {"voltage": "cycles", "dqdv": "ica", "dvdq": "dva"}.get(spec.curve_kind, "cycles")
        kwargs = {"cycles": list(spec.cycles)}
        if kind == "cycles":
            kwargs["mode"] = spec.mode
            kwargs["method"] = spec.method
        else:
            kwargs["direction"] = spec.direction
            kwargs["voltage_resolution"] = spec.voltage_resolution
        return _cells_cfz(records, kind, kwargs)
    return figure_bytes(plotting.cycles_figure(records, spec), fmt)


def compare_export(
    picks: plotting.ComparePicks, spec: ComparePlotSpec, fmt: str
) -> tuple[bytes, str]:
    """Rows for exactly the picked ``(cell, cycle)`` pairs the chart shows (#169)."""
    collection, reports = plotting.compare_collection(picks, spec)
    if collection is None:
        if reports:
            # Same wording as the chart: say which cycles the cells lack (#175).
            raise ValueError(
                "Nothing to export — " + "; ".join(r.message() for r in reports) + "."
            )
        raise ValueError("Pick one or more cycles to export.")
    if spec.curve_kind in ("dqdv", "dvdq"):
        collection = collect.select_ica_direction(collection, spec.direction)
    return collect.export_bytes(collection, fmt)


def compare_figure_export(
    picks: plotting.ComparePicks, spec: ComparePlotSpec, fmt: str
) -> tuple[bytes, str]:
    if fmt.lower() == "cfz":
        if spec.layout == "overlay":
            return _overlay_cfz(picks, spec)
        return _compare_cells_cfz(picks, spec)
    return figure_bytes(plotting.compare_figure(picks, spec), fmt)


def ica_export(record: CellRecord, spec: IcaPlotSpec, fmt: str) -> tuple[bytes, str]:
    collection = collect.ica_collection(
        [record],
        cycles=tuple(sorted(set(spec.cycles))),
        voltage_resolution=spec.voltage_resolution,
    )
    # Match the chart: charge/discharge filter the exported rows, "both" keeps all.
    collection = collect.select_ica_direction(collection, spec.direction)
    return collect.export_bytes(collection, fmt)


def ica_figure_export(
    record: CellRecord, spec: IcaPlotSpec, fmt: str
) -> tuple[bytes, str]:
    if fmt.lower() == "cfz":
        if not spec.cycles:
            raise FigureExportError("Pick one or more cycles to export.")
        return _cells_cfz(
            [record],
            "ica",
            {
                "cycles": list(spec.cycles),
                "direction": spec.direction,
                "voltage_resolution": spec.voltage_resolution,
            },
        )
    return figure_bytes(plotting.ica_figure(record, spec), fmt)


def dva_export(record: CellRecord, spec: DvaPlotSpec, fmt: str) -> tuple[bytes, str]:
    collection = collect.dva_collection(
        [record],
        cycles=tuple(sorted(set(spec.cycles))),
        voltage_resolution=spec.voltage_resolution,
    )
    # Same as ICA: charge/discharge slice the rows, "both" keeps them all.
    collection = collect.select_ica_direction(collection, spec.direction)
    return collect.export_bytes(collection, fmt)


def dva_figure_export(
    record: CellRecord, spec: DvaPlotSpec, fmt: str
) -> tuple[bytes, str]:
    if fmt.lower() == "cfz":
        if not spec.cycles:
            raise FigureExportError("Pick one or more cycles to export.")
        return _cells_cfz(
            [record],
            "dva",
            {
                "cycles": list(spec.cycles),
                "direction": spec.direction,
                "voltage_resolution": spec.voltage_resolution,
            },
        )
    return figure_bytes(plotting.dva_figure(record, spec), fmt)


_CFZ_DISABLED = (
    "cfz export needs cellpy.plotting.bundle.save_bundle. "
    'Install it with pip install "cellpy[plotting-mpl]".'
)


def _save_bundle(cell, **kwargs):
    from cellpy.plotting.bundle import save_bundle

    return save_bundle(cell, **kwargs)


def _cells_cfz(records: list[CellRecord], kind: str, kwargs: dict) -> tuple[bytes, str]:
    """Write one ``.cfz`` per cell through cellpy's translator.

    One cell returns that bundle. Several cells return a zip of bundles.
    """
    if not records:
        raise FigureExportError("No cells to export.")
    if not collect.cfz_export_available():
        raise FigureExportError(_CFZ_DISABLED)

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        written: list[tuple[str, Path]] = []
        for record, stem in zip(records, _unique_stems(records), strict=True):
            path = work / f"{stem}.cfz"
            _save_bundle(record.cell, kind=kind, path=str(path), **kwargs)
            written.append((path.name, path))
        if len(written) == 1:
            return written[0][1].read_bytes(), "application/zip"
        return _zip_members(written), "application/zip"


def _overlay_cfz(picks: plotting.ComparePicks, spec: ComparePlotSpec) -> tuple[bytes, str]:
    """The compare-overlay view, written from the tidy rows the chart uses.

    ``collect._overlay_facets`` restyles cellpy's facets after they come back,
    so this view does not go through ``save_bundle``.
    """
    collection, _reports = plotting.compare_collection(picks, spec)
    if collection is None or getattr(getattr(collection, "data", None), "height", 0) == 0:
        raise FigureExportError("Nothing to export.")
    if spec.curve_kind in ("dqdv", "dvdq"):
        collection = collect.select_ica_direction(collection, spec.direction)
    frame, x, y, labels = _overlay_table(collection.data, spec)
    return (
        overlay_bundle_bytes(
            frame,
            x=x,
            y=y,
            x_label=labels[0],
            y_label=labels[1],
            x_unit=labels[2],
            y_unit=labels[3],
            color="curve",
        ),
        "application/zip",
    )


def _compare_cells_cfz(picks: plotting.ComparePicks, spec: ComparePlotSpec) -> tuple[bytes, str]:
    """One ``save_bundle`` per cell when the compare view is still faceted."""
    kind = {"voltage": "cycles", "dqdv": "ica", "dvdq": "dva"}.get(spec.curve_kind, "cycles")
    written_records: list[CellRecord] = []
    bundles: list[bytes] = []
    for record, cycles in picks:
        if not cycles:
            continue
        kwargs: dict = {"cycles": list(cycles)}
        if kind == "cycles":
            kwargs["mode"] = spec.mode
            kwargs["method"] = spec.method
        else:
            kwargs["direction"] = spec.direction
            kwargs["voltage_resolution"] = spec.voltage_resolution
        data, _media = _cells_cfz([record], kind, kwargs)
        written_records.append(record)
        bundles.append(data)
    if not bundles:
        raise FigureExportError("Nothing to export.")
    if len(bundles) == 1:
        return bundles[0], "application/zip"
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        members = []
        for record, stem, data in zip(written_records, _unique_stems(written_records), bundles, strict=True):
            path = work / f"{stem}.cfz"
            path.write_bytes(data)
            members.append((path.name, path))
        return _zip_members(members), "application/zip"


def _overlay_table(data, spec: ComparePlotSpec):
    """Tidy rows plus the x/y columns the overlay chart is showing."""
    import polars as pl

    from .models import CAPACITY_UNITS

    columns = set(data.columns)
    cycle_col = next((name for name in ("cycle_num", "cycle") if name in columns), None)
    if "cell" not in columns or cycle_col is None:
        raise FigureExportError("Overlay export needs cell and cycle columns.")
    if spec.curve_kind == "dqdv":
        x = "voltage" if "voltage" in columns else "potential"
        y, x_label, y_label = "dqdv", "Voltage", "dQ/dV"
        x_unit, y_unit = "V", None
    elif spec.curve_kind == "dvdq":
        x, y, x_label, y_label = "capacity", "dvdq", "Capacity", "dV/dQ"
        x_unit = CAPACITY_UNITS.get(spec.mode, CAPACITY_UNITS["gravimetric"])
        y_unit = None
    else:
        x = "capacity"
        y = "voltage" if "voltage" in columns else "potential"
        x_label, y_label = "Capacity", "Voltage"
        x_unit = CAPACITY_UNITS.get(spec.mode, CAPACITY_UNITS["gravimetric"])
        y_unit = "V"
    missing = [name for name in (x, y) if name not in columns]
    if missing:
        raise FigureExportError(
            "Overlay export cannot find " + ", ".join(missing) + " in the collected rows."
        )
    frame = data.with_columns(
        (
            pl.col("cell").cast(pl.Utf8)
            + " · "
            + pl.col(cycle_col).cast(pl.Utf8)
        ).alias("curve")
    )
    return frame, x, y, (x_label, y_label, x_unit, y_unit)


def overlay_bundle_bytes(
    frame,
    *,
    x: str,
    y: str,
    x_label: str | None = None,
    y_label: str | None = None,
    x_unit: str | None = None,
    y_unit: str | None = None,
    color: str | None = None,
    facet: str | None = None,
) -> bytes:
    """Write a compare-overlay bundle the GUI assembled itself.

    cellpy's ``save_bundle`` does not see this view, because the GUI restyles
    the facets after cellpy returns them. ``provenance.producer`` is
    ``cellpy-simple-gui``.
    """
    try:
        import cellpy_simple_gui
        from cellpy_figure import Encoding, Figure, Panel, Provenance
    except ImportError as exc:
        raise FigureExportError(_CFZ_DISABLED) from exc

    panel = Panel(
        x=Encoding(field=x, label=x_label or x, unit=x_unit),
        y=Encoding(field=y, label=y_label or y, unit=y_unit),
        color=Encoding(field=color, type="nominal", legend_title="Curve") if color else None,
        facet=Encoding(field=facet, label=facet) if facet else None,
    )
    figure = Figure(
        data=frame,
        panels=[panel],
        provenance=Provenance(
            producer="cellpy-simple-gui",
            producer_version=cellpy_simple_gui.__version__,
        ),
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "overlay.cfz"
        figure.write(str(path))
        return path.read_bytes()


def figure_bytes(figure_json: str, fmt: str) -> tuple[bytes, str]:
    """Render Plotly figure JSON to static image bytes (requires kaleido).

    Delegates the encode to cellpy's in-memory ``figures.write_image`` (#818),
    which uses ``figure.to_image`` directly — no temp files or subprocess.
    """
    fmt = fmt.lower()
    if fmt not in collect.FIGURE_EXPORT_FORMATS:
        raise FigureExportError(
            f"Unsupported figure format '{fmt}'. "
            f"Use one of {collect.FIGURE_EXPORT_FORMATS}."
        )
    try:
        fig = pio.from_json(figure_json)
    except Exception as exc:  # noqa: BLE001
        raise FigureExportError(f"Could not load figure for export ({exc}).") from exc

    try:
        data = cellpy_figures.write_image(fig, fmt, scale=2)
    except OptionalDependencyError as exc:
        raise FigureExportError(_MISSING_KALEIDO, missing_kaleido=True) from exc
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).lower()
        # kaleido 1.x renders by driving a *separate* Chrome, so "kaleido is
        # installed" and "figure export works" are different facts. Telling
        # someone to install kaleido when kaleido is already there and the
        # browser is what is missing sends them the wrong way — which is
        # exactly what happens in a container (#121).
        if any(k in msg for k in ("chrome", "chromium", "browser")):
            raise FigureExportError(_MISSING_BROWSER, missing_kaleido=True) from exc
        if any(k in msg for k in ("kaleido", "orca", "image export")):
            raise FigureExportError(_MISSING_KALEIDO, missing_kaleido=True) from exc
        raise FigureExportError(f"Figure export failed ({exc}).") from exc

    if not data:
        raise FigureExportError("Figure export produced an empty file.")
    return data, cellpy_figures.image_media_type(fmt)


def _safe_stem(record: CellRecord) -> str:
    raw = (record.label or record.name or record.id or "cell").strip() or "cell"
    stem = _SAFE_STEM.sub("_", raw).strip("._") or "cell"
    return stem[:80]


def _unique_stems(records: list[CellRecord]) -> list[str]:
    """Stable, filesystem-safe stems; disambiguate duplicates with ``_2``, …"""
    counts: dict[str, int] = {}
    out: list[str] = []
    for rec in records:
        base = _safe_stem(rec)
        n = counts.get(base, 0) + 1
        counts[base] = n
        out.append(base if n == 1 else f"{base}_{n}")
    return out


def _zip_members(members: list[tuple[str, Path]]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for arcname, path in members:
            zf.write(path, arcname)
    return buf.getvalue()


def _export_one_cell(
    record: CellRecord, fmt: str, work: Path, stem: str
) -> list[tuple[str, Path]]:
    """Write one cell into ``work``; return (archive_name, path) pairs."""
    cell_dir = work / stem
    cell_dir.mkdir(parents=True, exist_ok=True)
    if fmt == "cellpy":
        path = cell_dir / f"{stem}.cellpy"
        cellpy_adapter.save_cell(record.cell, path)
        return [(path.name, path)]
    if fmt == "xlsx":
        path = cell_dir / f"{stem}.xlsx"
        cellpy_adapter.export_cell_excel(record.cell, path)
        return [(path.name, path)]
    if fmt == "csv":
        files = cellpy_adapter.export_cell_csv(record.cell, cell_dir)
        if not files:
            raise RuntimeError(f"cellpy to_csv produced no files for “{stem}”.")
        return [(f"{stem}/{p.name}", p) for p in files]
    raise ValueError(f"Unsupported cell export format '{fmt}'.")


def cells_export(records: list[CellRecord], fmt: str) -> tuple[bytes, str, str]:
    """Export library cells via cellpy save/to_csv/to_excel.

    Returns ``(bytes, media_type, download_filename)``. One cellpy/xlsx file is
    returned bare; csv (often multi-file) and multi-cell exports are zipped.
    """
    fmt = fmt.lower()
    if fmt not in CELL_EXPORT_FORMATS:
        raise ValueError(
            f"Unsupported cell export format '{fmt}'. Use one of {CELL_EXPORT_FORMATS}."
        )
    if not records:
        raise ValueError("No cells to export.")

    stems = _unique_stems(records)
    with tempfile.TemporaryDirectory(prefix="csg-cells-export-") as tmp:
        work = Path(tmp)
        members: list[tuple[str, Path]] = []
        for rec, stem in zip(records, stems, strict=True):
            chunk = _export_one_cell(rec, fmt, work, stem)
            if len(records) == 1:
                members.extend(chunk)
            else:
                for arc, path in chunk:
                    name = arc if "/" in arc or "\\" in arc else f"{stem}/{arc}"
                    members.append((name.replace("\\", "/"), path))

        if len(records) == 1 and fmt in ("cellpy", "xlsx") and len(members) == 1:
            path = members[0][1]
            return path.read_bytes(), _CELL_MEDIA[fmt], members[0][0]

        stem0 = stems[0] if len(records) == 1 else "cells"
        filename = f"{stem0}_{fmt}.zip" if len(records) == 1 else f"cells_{fmt}.zip"
        return _zip_members(members), _CELL_MEDIA["zip"], filename
