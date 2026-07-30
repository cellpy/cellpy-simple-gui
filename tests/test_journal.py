"""Tests for loading native cellpy batch journals."""

from __future__ import annotations

import pandas as pd
import pytest


def _build_journal(tmp_path):
    """Write a real cellpy batch journal referencing the bundled example files."""
    from cellpy import batch as cbatch
    from cellpy.utils import example_data

    p1 = example_data.cellpy_file_path()
    p2 = example_data.rate_file()
    frame = pd.DataFrame(
        {
            "filename": ["cellA", "cellB"],
            "cellpy_file_name": [str(p1), str(p2)],
            "group": [1, 2],
            "sub_group": [1, 1],
            "selected": [True, True],
            "label": ["cellA", "cellB"],
        }
    )
    journal = cbatch.journal_from_frame(frame)
    path = tmp_path / "journal.json"
    cbatch.write_journal(journal, path)
    return path


def test_load_journal_cells(tmp_path):
    from cellpy_simple_gui.core import cellpy_adapter

    try:
        path = _build_journal(tmp_path)
    except Exception as exc:  # noqa: BLE001 - offline / example data missing
        pytest.skip(f"example data unavailable: {exc}")

    triples = cellpy_adapter.load_journal_cells(path)
    assert len(triples) == 2
    labels = {label for label, _cell, _group in triples}
    assert labels == {"cellA", "cellB"}
    groups = {label: group for label, _cell, group in triples}
    assert groups["cellB"] == 2
    # cells carry real data
    for _label, cell, _group in triples:
        assert cell.get_number_of_cycles() > 0


def test_load_journal_missing_files_returns_empty(tmp_path):
    """A journal pointing at non-existent .cellpy files yields no linkable cells."""
    from cellpy import batch as cbatch
    from cellpy_simple_gui.core import cellpy_adapter

    frame = pd.DataFrame(
        {
            "filename": ["ghost"],
            "cellpy_file_name": [str(tmp_path / "ghost.cellpy")],
            "group": [1],
            "sub_group": [1],
            "selected": [True],
            "label": ["ghost"],
        }
    )
    path = tmp_path / "bad.json"
    cbatch.write_journal(cbatch.journal_from_frame(frame), path)

    triples = cellpy_adapter.load_journal_cells(path)
    assert triples == []


def test_load_corrupt_journal_raises_clear_error(tmp_path):
    from cellpy_simple_gui.core import cellpy_adapter

    path = tmp_path / "corrupt.json"
    path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Could not parse batch journal"):
        cellpy_adapter.load_journal_cells(path)


def test_api_load_corrupt_journal_reports_error(tmp_path):
    """Job must finish with an errors[] payload the UI can toast — not hang."""
    import time

    from fastapi.testclient import TestClient

    from cellpy_simple_gui.api.app import create_app
    from cellpy_simple_gui.config import get_settings
    from cellpy_simple_gui.core.library import get_library

    path = tmp_path / "corrupt.json"
    path.write_text("{not valid json", encoding="utf-8")

    get_library().clear()
    client = TestClient(create_app())
    client.headers.update({"X-CSG-Token": get_settings().token})
    job_id = client.post("/api/projects/load-journal", json={"path": str(path)}).json()["job_id"]

    deadline = time.time() + 30
    while time.time() < deadline:
        snap = client.get(f"/api/jobs/{job_id}").json()
        if snap["status"] in ("done", "error", "cancelled"):
            break
        time.sleep(0.1)
    else:
        raise AssertionError("journal job did not finish")

    assert snap["status"] == "done"
    assert snap["result"]["added"] == []
    assert any("Failed to load journal" in e for e in snap["result"]["errors"])
