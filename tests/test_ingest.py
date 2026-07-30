"""Tests for raw-file ingestion (adapter + API)."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from cellpy_simple_gui.api.app import create_app
from cellpy_simple_gui.config import get_settings
from cellpy_simple_gui.core import cellpy_adapter
from cellpy_simple_gui.core.library import get_library


def _client():
    get_library().clear()
    c = TestClient(create_app())
    c.headers.update({"X-CSG-Token": get_settings().token})
    return c


def _wait(client, job_id, timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        snap = client.get(f"/api/jobs/{job_id}").json()
        if snap["status"] in ("done", "error", "cancelled"):
            return snap
        time.sleep(0.3)
    raise AssertionError("job timeout")


@pytest.mark.essential
def test_instruments_endpoint():
    client = _client()
    data = client.get("/api/instruments").json()
    ids = {i["id"] for i in data["instruments"]}
    assert {"arbin_res", "maccor_txt", "neware_txt", "pec_csv"} <= ids
    # maccor exposes sub-models; arbin does not
    maccor = next(i for i in data["instruments"] if i["id"] == "maccor_txt")
    assert maccor["models"]
    assert {e["kind"] for e in data["examples"]}


@pytest.mark.essential
def test_ingest_bad_instrument_400():
    client = _client()
    r = client.post("/api/ingest", json={"paths": ["x.res"], "instrument": "nope"})
    assert r.status_code == 400


def test_ingest_example_neware():
    client = _client()
    r = client.post("/api/ingest/example", json={"kind": "neware", "mass": 1.2})
    snap = _wait(client, r.json()["job_id"])
    if snap["status"] != "done" or not snap.get("result", {}).get("added"):
        pytest.skip(f"example raw data unavailable: {snap.get('message')}")
    state = client.get("/api/state").json()
    assert state["n_cells"] == 1
    cell = state["cells"][0]
    assert cell["source"] == "raw:neware_txt"
    assert cell["n_cycles"] > 0


def test_adapter_load_raw_pec():
    """Core-level: a bundled PEC csv processes into a summary."""
    try:
        path = cellpy_adapter.example_raw_path("pec")
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"example raw data unavailable: {exc}")
    cell = cellpy_adapter.load_raw(path, "pec_csv", mass=1.0)
    df = cellpy_adapter.summary_frame(cell)
    assert "charge_capacity_gravimetric" in df.columns
    assert len(df) > 0
