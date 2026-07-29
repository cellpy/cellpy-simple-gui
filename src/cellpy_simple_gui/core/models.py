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
    mode: CapacityMode = "gravimetric"
    direction: Direction = "charge"
    show_efficiency: bool = True
    show_capacity_loss: bool = False
    group_colors: bool = True
    markers: bool = True
    title: str = "Cycle summary"


class CyclesPlotSpec(BaseModel):
    cell_id: str
    cycles: list[int] = Field(default_factory=list)
    mode: CapacityMode = "gravimetric"
    method: CycleMethod = "forth-and-forth"
    title: str = ""


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
