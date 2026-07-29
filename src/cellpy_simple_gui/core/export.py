"""Data export — serialise cellpy collections to csv / xlsx / parquet / json."""

from __future__ import annotations

from . import collect
from .library import CellRecord
from .models import CyclesPlotSpec, SummaryPlotSpec


def summary_export(records: list[CellRecord], spec: SummaryPlotSpec, fmt: str) -> tuple[bytes, str]:
    columns = collect.summary_columns(
        spec.basis, spec.show_charge, spec.show_discharge, spec.show_efficiency
    )
    collection = collect.summary_collection(
        records, columns=columns, group_it=spec.group_average, max_cycle=spec.max_cycle
    )
    return collect.export_bytes(collection, fmt)


def cycles_export(record: CellRecord, spec: CyclesPlotSpec, fmt: str) -> tuple[bytes, str]:
    collection = collect.cycles_collection(
        [record], cycles=tuple(sorted(set(spec.cycles)))
    )
    return collect.export_bytes(collection, fmt)
