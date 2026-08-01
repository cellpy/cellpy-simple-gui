"""Data + static-figure export.

Data path: cellpy collections → csv / xlsx / parquet / json.
Figure path: Plotly figure JSON → png / svg / pdf via kaleido (`fig.write_image`).
Library cells: cellpy ``save`` / ``to_csv`` / ``to_excel`` → bytes (often zipped).
cellpy has no in-memory collect-level image API yet (see CELLPY_PAINPOINTS §13).
"""

from __future__ import annotations

import io
import re
import tempfile
import zipfile
from pathlib import Path

import plotly.io as pio

from . import cellpy_adapter, collect, plotting
from .library import CellRecord
from .models import CyclesPlotSpec, IcaPlotSpec, SummaryPlotSpec

CELL_EXPORT_FORMATS = ("cellpy", "csv", "xlsx")
_CELL_MEDIA = {
    "cellpy": "application/octet-stream",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "zip": "application/zip",
}
_SAFE_STEM = re.compile(r"[^\w.\-]+", re.UNICODE)


class FigureExportError(RuntimeError):
    """Static figure export failed (often missing kaleido)."""

    def __init__(self, message: str, *, missing_kaleido: bool = False):
        super().__init__(message)
        self.missing_kaleido = missing_kaleido


def summary_export(records: list[CellRecord], spec: SummaryPlotSpec, fmt: str) -> tuple[bytes, str]:
    columns = collect.summary_columns_for(spec.plot_type, spec.basis)
    parts = collect.summary_collections(
        records,
        columns=columns,
        group_it=spec.group_average,
        max_cycle=spec.max_cycle,
    )
    if len(parts) == 1:
        return collect.export_bytes(parts[0][0], fmt)
    frame = collect.combined_summary_frame(parts, columns)
    return collect.export_frame_bytes(frame, fmt)


def cycles_export(records: list[CellRecord], spec: CyclesPlotSpec, fmt: str) -> tuple[bytes, str]:
    collection = collect.cycles_collection(
        records, cycles=tuple(sorted(set(spec.cycles))), mode=spec.mode, method=spec.method
    )
    return collect.export_bytes(collection, fmt)


def summary_figure_export(
    records: list[CellRecord], spec: SummaryPlotSpec, fmt: str
) -> tuple[bytes, str]:
    return figure_bytes(plotting.summary_figure(records, spec), fmt)


def cycles_figure_export(
    records: list[CellRecord], spec: CyclesPlotSpec, fmt: str
) -> tuple[bytes, str]:
    return figure_bytes(plotting.cycles_figure(records, spec), fmt)


def ica_export(record: CellRecord, spec: IcaPlotSpec, fmt: str) -> tuple[bytes, str]:
    collection = collect.ica_collection(
        [record],
        cycles=tuple(sorted(set(spec.cycles))),
        voltage_resolution=spec.voltage_resolution,
        direction=spec.direction,
    )
    return collect.export_bytes(collection, fmt)


def ica_figure_export(
    record: CellRecord, spec: IcaPlotSpec, fmt: str
) -> tuple[bytes, str]:
    return figure_bytes(plotting.ica_figure(record, spec), fmt)


def figure_bytes(figure_json: str, fmt: str) -> tuple[bytes, str]:
    """Render Plotly figure JSON to static image bytes (requires kaleido)."""
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

    buf = io.BytesIO()
    try:
        fig.write_image(buf, format=fmt, scale=2)
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).lower()
        missing = (
            _kaleido_missing()
            or isinstance(exc, ImportError)
            or "kaleido" in msg
            or "orca" in msg
            or "chromium" in msg
            or "image export" in msg
        )
        if missing:
            raise FigureExportError(
                "Static figure export needs kaleido. "
                "Install with: uv sync --extra export",
                missing_kaleido=True,
            ) from exc
        raise FigureExportError(f"Figure export failed ({exc}).") from exc

    data = buf.getvalue()
    if not data:
        raise FigureExportError("Figure export produced an empty file.")
    return data, collect._MEDIA[fmt]


def _kaleido_missing() -> bool:
    try:
        import kaleido  # noqa: F401
    except ImportError:
        return True
    return False


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
