"""Shared test fixtures.

The example cells are downloaded from GitHub on first use and then cached by
cellpy. If there is no network and no cache, the cellpy-dependent tests skip
rather than fail.
"""

from __future__ import annotations

import json

import pytest


@pytest.fixture(scope="session")
def example_cell():
    from cellpy_simple_gui.core import cellpy_adapter

    try:
        return cellpy_adapter.load_example("cellpy")
    except Exception as exc:  # noqa: BLE001 - offline / download failure
        pytest.skip(f"example data unavailable: {exc}")


@pytest.fixture()
def loaded_library(example_cell):
    from cellpy_simple_gui.core.library import Library

    lib = Library()
    lib.add_cell(example_cell, source="example:cellpy")
    return lib


def parse_figure(figure_json: str) -> dict:
    return json.loads(figure_json)
