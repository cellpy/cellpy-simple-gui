"""`.cfz` export beside png, svg, and pdf (cellpy/cellpy-simple-gui#196)."""

from __future__ import annotations

import io
import json
import zipfile

import pandas as pd
import polars as pl
import pytest

from cellpy_simple_gui.core import collect, export, plotting
from cellpy_simple_gui.core.library import CellRecord
from cellpy_simple_gui.core.models import (
    ComparePlotSpec,
    CyclesPlotSpec,
    DvaPlotSpec,
    IcaPlotSpec,
    SummaryPlotSpec,
)


def _record() -> CellRecord:
    return CellRecord(id="a", cell=object(), name="alpha", label="alpha")


def _write_bundle(cell, *, kind, path, **kwargs):
    from cellpy_figure import Encoding, Figure, Panel, Provenance

    figure = Figure(
        data=pd.DataFrame({"cycle_index": [1], "value": [2.0]}),
        panels=[
            Panel(
                x=Encoding(field="cycle_index", label="Cycle"),
                y=Encoding(field="value", label="Value"),
            )
        ],
        provenance=Provenance(producer="cellpy", producer_version="test"),
        extensions={"cellpy": {"family": kind}},
    )
    figure.write(path)
    return path


def _names(data: bytes) -> set[str]:
    return set(zipfile.ZipFile(io.BytesIO(data)).namelist())


def _figure(data: bytes) -> dict:
    return json.loads(zipfile.ZipFile(io.BytesIO(data)).read("figure.json"))


def test_cfz_is_absent_when_the_translator_is_missing(monkeypatch):
    monkeypatch.setattr(collect, "cfz_export_available", lambda: False)
    monkeypatch.setattr(plotting, "summary_figure", lambda records, spec: "{}")
    monkeypatch.setattr(export, "figure_bytes", lambda figure, fmt: (b"PNG", "image/png"))

    assert "cfz" not in collect.figure_export_formats()
    assert collect.FIGURE_EXPORT_FORMATS == ("png", "svg", "pdf")
    data, media = export.summary_figure_export([_record()], SummaryPlotSpec(), "png")
    assert data == b"PNG" and media == "image/png"
    with pytest.raises(export.FigureExportError, match="save_bundle"):
        export.summary_figure_export([_record()], SummaryPlotSpec(), "cfz")


def test_one_cell_cfz_is_the_bundle(monkeypatch):
    monkeypatch.setattr(collect, "cfz_export_available", lambda: True)
    monkeypatch.setattr(export, "_save_bundle", _write_bundle)
    data, media = export.summary_figure_export([_record()], SummaryPlotSpec(), "cfz")
    assert media == "application/zip"
    assert {"manifest.json", "figure.json", "data.parquet"} <= _names(data)
    manifest = json.loads(zipfile.ZipFile(io.BytesIO(data)).read("manifest.json"))
    assert manifest["format_version"] == 1
    assert _figure(data)["provenance"]["producer"] == "cellpy"


def test_ica_and_dva_and_cycles_use_the_translator(monkeypatch):
    seen = []

    def spy(cell, *, kind, path, **kwargs):
        seen.append(kind)
        return _write_bundle(cell, kind=kind, path=path, **kwargs)

    monkeypatch.setattr(collect, "cfz_export_available", lambda: True)
    monkeypatch.setattr(export, "_save_bundle", spy)
    record = _record()
    export.cycles_figure_export([record], CyclesPlotSpec(cycles=[1]), "cfz")
    export.ica_figure_export(record, IcaPlotSpec(cell_id=record.id, cycles=[1]), "cfz")
    export.dva_figure_export(record, DvaPlotSpec(cell_id=record.id, cycles=[1]), "cfz")
    assert seen == ["cycles", "ica", "dva"]


def test_index_omits_cfz_when_the_translator_is_missing(monkeypatch):
    monkeypatch.setattr(collect, "cfz_export_available", lambda: False)
    from fastapi.testclient import TestClient

    from cellpy_simple_gui.api.app import create_app

    html = TestClient(create_app()).get("/").text
    assert 'name="csg-figure-formats"' in html
    assert "cfz" not in html.split('name="csg-figure-formats"', 1)[1].split(">", 1)[0]


def test_overlay_export_names_the_gui(monkeypatch):
    frame = pl.DataFrame(
        {
            "cell": ["a", "b"],
            "cycle_num": [1, 7],
            "capacity": [1.0, 2.0],
            "voltage": [3.0, 3.1],
        }
    )

    class _Collection:
        data = frame

    monkeypatch.setattr(
        plotting, "compare_collection", lambda picks, spec: (_Collection(), [])
    )
    spec = ComparePlotSpec(
        picks=[{"cell_id": "a", "cycles": [1]}],
        layout="overlay",
    )
    data, media = export.compare_figure_export([], spec, "cfz")
    assert media == "application/zip"
    assert {"manifest.json", "figure.json", "data.parquet"} <= _names(data)
    figure = _figure(data)
    assert figure["provenance"]["producer"] == "cellpy-simple-gui"
    assert figure["panels"][0]["color"]["field"] == "curve"
