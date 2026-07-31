"""Export endpoints: collected data, library cells, and static figures."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from ...core import collect, export as export_core
from ...core.library import get_library
from ...core.models import CellsExportSpec, CyclesPlotSpec, IcaPlotSpec, SummaryPlotSpec

log = logging.getLogger(__name__)
router = APIRouter()

_DATA_EXT = {"csv": "csv", "xlsx": "xlsx", "parquet": "parquet", "json": "json"}
_FIG_EXT = {f: f for f in collect.FIGURE_EXPORT_FORMATS}


def _check_data_fmt(fmt: str) -> str:
    fmt = fmt.lower()
    if fmt not in collect.EXPORT_FORMATS:
        raise HTTPException(
            400,
            f"Unsupported format '{fmt}'. "
            f"Data: {collect.EXPORT_FORMATS}; figures: {collect.FIGURE_EXPORT_FORMATS}.",
        )
    return fmt


def _check_figure_fmt(fmt: str) -> str:
    fmt = fmt.lower()
    if fmt not in collect.FIGURE_EXPORT_FORMATS:
        raise HTTPException(
            400,
            f"Unsupported figure format '{fmt}'. Use one of {collect.FIGURE_EXPORT_FORMATS}.",
        )
    return fmt


def _file(data: bytes, media: str, name: str) -> Response:
    return Response(
        content=data,
        media_type=media,
        headers={"Content-Disposition": f"attachment; filename={name}"},
    )


def _figure_http(exc: export_core.FigureExportError) -> HTTPException:
    status = 503 if exc.missing_kaleido else 400
    return HTTPException(status, str(exc))


@router.post("/export/summary")
def export_summary(spec: SummaryPlotSpec, fmt: str = "csv") -> Response:
    fmt_l = fmt.lower()
    records = get_library().selected()
    if not records:
        raise HTTPException(400, "No cells selected.")
    log.info("Export summary as %s (%d selected)", fmt_l, len(records))
    if fmt_l in collect.FIGURE_EXPORT_FORMATS:
        fmt_l = _check_figure_fmt(fmt_l)
        try:
            data, media = export_core.summary_figure_export(records, spec, fmt_l)
        except export_core.FigureExportError as exc:
            log.error("Summary figure export failed: %s", exc)
            raise _figure_http(exc) from exc
        return _file(data, media, f"summary.{_FIG_EXT[fmt_l]}")
    fmt_l = _check_data_fmt(fmt_l)
    data, media = export_core.summary_export(records, spec, fmt_l)
    return _file(data, media, f"summary.{_DATA_EXT[fmt_l]}")


def _cycles_records(spec: CyclesPlotSpec):
    lib = get_library()
    if spec.cell_id:
        try:
            return [lib.get(spec.cell_id)]
        except KeyError:
            raise HTTPException(404, "No such cell")
    return lib.selected()


@router.post("/export/cycles")
def export_cycles(spec: CyclesPlotSpec, fmt: str = "csv") -> Response:
    fmt_l = fmt.lower()
    records = _cycles_records(spec)
    if not records:
        raise HTTPException(400, "Select one or more cells to export cycles.")
    if len(records) == 1:
        name = f"cycles_{(records[0].label or records[0].name)}".replace(" ", "_")
    else:
        name = f"cycles_{len(records)}_cells"
    if fmt_l in collect.FIGURE_EXPORT_FORMATS:
        fmt_l = _check_figure_fmt(fmt_l)
        try:
            data, media = export_core.cycles_figure_export(records, spec, fmt_l)
        except export_core.FigureExportError as exc:
            raise _figure_http(exc) from exc
        return _file(data, media, f"{name}.{_FIG_EXT[fmt_l]}")
    fmt_l = _check_data_fmt(fmt_l)
    data, media = export_core.cycles_export(records, spec, fmt_l)
    return _file(data, media, f"{name}.{_DATA_EXT[fmt_l]}")


@router.post("/export/ica")
def export_ica(spec: IcaPlotSpec, fmt: str = "csv") -> Response:
    fmt_l = fmt.lower()
    try:
        rec = get_library().get(spec.cell_id)
    except KeyError:
        raise HTTPException(404, "No such cell")
    name = f"ica_{(rec.label or rec.name)}".replace(" ", "_")
    if fmt_l in collect.FIGURE_EXPORT_FORMATS:
        fmt_l = _check_figure_fmt(fmt_l)
        try:
            data, media = export_core.ica_figure_export(rec, spec, fmt_l)
        except export_core.FigureExportError as exc:
            raise _figure_http(exc) from exc
        return _file(data, media, f"{name}.{_FIG_EXT[fmt_l]}")
    fmt_l = _check_data_fmt(fmt_l)
    data, media = export_core.ica_export(rec, spec, fmt_l)
    return _file(data, media, f"{name}.{_DATA_EXT[fmt_l]}")


@router.post("/export/cells")
def export_cells(spec: CellsExportSpec | None = None, fmt: str = "cellpy") -> Response:
    """Export selected (or listed) library cells via cellpy save/to_csv/to_excel."""
    fmt_l = fmt.lower()
    if fmt_l not in export_core.CELL_EXPORT_FORMATS:
        raise HTTPException(
            400,
            f"Unsupported cell format '{fmt}'. Use one of {export_core.CELL_EXPORT_FORMATS}.",
        )
    lib = get_library()
    if spec and spec.cell_ids:
        records = []
        for cid in spec.cell_ids:
            try:
                records.append(lib.get(cid))
            except KeyError:
                raise HTTPException(404, f"No such cell: {cid}") from None
    else:
        records = lib.selected()
    if not records:
        raise HTTPException(400, "No cells selected.")
    log.info("Export %d cell(s) as %s", len(records), fmt_l)
    try:
        data, media, filename = export_core.cells_export(records, fmt_l)
    except Exception as exc:  # noqa: BLE001 - surface cellpy/IO failures cleanly
        log.error("Cell export failed: %s", exc)
        raise HTTPException(500, f"Cell export failed: {exc}") from exc
    return _file(data, media, filename)
