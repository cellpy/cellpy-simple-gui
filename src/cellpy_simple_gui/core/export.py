"""Data + static-figure export.

Data path: cellpy collections → csv / xlsx / parquet / json.
Figure path: Plotly figure JSON → png / svg / pdf via kaleido (`fig.write_image`).
cellpy has no in-memory collect-level image API yet (see CELLPY_PAINPOINTS §13).
"""

from __future__ import annotations

import io

import plotly.io as pio

from . import collect, plotting
from .library import CellRecord
from .models import CyclesPlotSpec, SummaryPlotSpec


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


def cycles_export(record: CellRecord, spec: CyclesPlotSpec, fmt: str) -> tuple[bytes, str]:
    collection = collect.cycles_collection(
        [record], cycles=tuple(sorted(set(spec.cycles))), mode=spec.mode, method=spec.method
    )
    return collect.export_bytes(collection, fmt)


def summary_figure_export(
    records: list[CellRecord], spec: SummaryPlotSpec, fmt: str
) -> tuple[bytes, str]:
    return figure_bytes(plotting.summary_figure(records, spec), fmt)


def cycles_figure_export(
    record: CellRecord, spec: CyclesPlotSpec, fmt: str
) -> tuple[bytes, str]:
    return figure_bytes(plotting.cycles_figure(record, spec), fmt)


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
