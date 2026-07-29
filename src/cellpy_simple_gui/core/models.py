"""Pydantic domain models shared by the core, the API and (as JSON) the UI."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

CapacityMode = Literal["gravimetric", "areal", "absolute"]
Direction = Literal["charge", "discharge"]
CycleMethod = Literal["forth-and-forth", "back-and-forth", "forth"]

# Human-friendly axis labels per capacity mode.
CAPACITY_UNITS: dict[CapacityMode, str] = {
    "gravimetric": "mAh/g",
    "areal": "mAh/cm²",
    "absolute": "mAh",
}


class CellMeta(BaseModel):
    """Everything the UI needs to know about one loaded cell.

    The heavy ``CellpyCell`` object lives in the in-memory library; this is the
    lightweight, serialisable projection of it.
    """

    id: str
    name: str
    source: str = "example"
    mass: float | None = None  # mg
    area: float | None = None  # cm^2
    nominal_capacity: float | None = None
    n_cycles: int = 0
    group: int = 1
    label: str = ""
    selected: bool = True
    color: str | None = None


class SummaryPlotSpec(BaseModel):
    """Drives a cellpy ``collect_summaries`` collection + its plot/export."""

    basis: CapacityMode = "gravimetric"
    show_charge: bool = True
    show_discharge: bool = True
    show_efficiency: bool = False
    group_average: bool = False  # average per group (affects data/export)
    spread: bool = False  # mean ± std band (when grouped)
    max_cycle: Optional[int] = None
    title: str = "Cycle summary"


class CyclesPlotSpec(BaseModel):
    """Drives a cellpy ``collect_cycles`` collection for one cell."""

    cell_id: str
    cycles: list[int] = Field(default_factory=list)
    title: str = ""


class ExportSpec(BaseModel):
    """A plot spec plus the desired file format."""

    fmt: str = "csv"  # csv | xlsx | parquet | json
    summary: Optional[SummaryPlotSpec] = None
    cycles: Optional[CyclesPlotSpec] = None


class JournalRowUpdate(BaseModel):
    """A single editable-grid change."""

    id: str
    group: Optional[int] = None
    label: Optional[str] = None
    selected: Optional[bool] = None
    mass: Optional[float] = None


class LoadExampleRequest(BaseModel):
    kinds: list[str] = Field(default_factory=lambda: ["cellpy", "old_cellpy", "rate"])


class LoadFilesRequest(BaseModel):
    paths: list[str]


CycleMode = Literal["anode", "cathode", "full_cell"]


class IngestRequest(BaseModel):
    """Import one or more raw instrument files with shared metadata."""

    paths: list[str]
    instrument: str
    model: Optional[str] = None
    mass: Optional[float] = None  # mg
    area: Optional[float] = None  # cm^2
    nominal_capacity: Optional[float] = None
    nom_cap_specifics: Optional[CapacityMode] = None
    cycle_mode: Optional[CycleMode] = None


class IngestExampleRequest(BaseModel):
    kind: str = "neware"  # one of cellpy_adapter.EXAMPLE_RAW
    mass: Optional[float] = None
