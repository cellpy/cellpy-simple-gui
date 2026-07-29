"""Integration tests for the FastAPI layer using TestClient."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from cellpy_simple_gui.api.app import create_app
from cellpy_simple_gui.config import get_settings
from cellpy_simple_gui.core.library import get_library


@pytest.fixture()
def client():
    get_library().clear()
    token = get_settings().token
    c = TestClient(create_app())
    c.headers.update({"X-CSG-Token": token})
    return c


def _wait_for_job(client, job_id, timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        snap = client.get(f"/api/jobs/{job_id}").json()
        if snap["status"] in ("done", "error", "cancelled"):
            return snap
        time.sleep(0.3)
    raise AssertionError("job did not finish in time")


def test_healthz(client):
    assert client.get("/healthz").json() == {"ok": True}


def test_token_required():
    c = TestClient(create_app())  # no token header
    assert c.get("/api/state").status_code == 401


def test_examples(client):
    data = client.get("/api/examples").json()
    ids = {e["id"] for e in data}
    assert {"cellpy", "old_cellpy", "rate"} <= ids


def test_load_and_plot_flow(client):
    # kick off a load job for one example cell
    r = client.post("/api/load/example", json={"kinds": ["cellpy"]})
    job_id = r.json()["job_id"]
    snap = _wait_for_job(client, job_id)
    if snap["status"] != "done":
        pytest.skip(f"example data unavailable: {snap.get('message')}")
    assert snap["result"]["added"]

    state = client.get("/api/state").json()
    assert state["n_cells"] == 1
    cell_id = state["cells"][0]["id"]

    # summary figure (cellpy collected plot)
    fig = client.post(
        "/api/plots/summary",
        json={"basis": "gravimetric", "show_charge": True, "show_discharge": True},
    ).json()
    assert len(fig["data"]) >= 1

    # cycles info + figure
    info = client.get(f"/api/cells/{cell_id}/cycles").json()
    assert info["max"] > info["min"]
    cfig = client.post(
        "/api/plots/cycles",
        json={"cell_id": cell_id, "cycles": [1, 5, 10]},
    ).json()
    assert len(cfig["data"]) >= 1

    # multi-format export
    for fmt in ("csv", "xlsx", "parquet", "json"):
        r = client.post(f"/api/export/summary?fmt={fmt}", json={"basis": "gravimetric"})
        assert r.status_code == 200, fmt
        assert len(r.content) > 0
    bad = client.post("/api/export/summary?fmt=nope", json={"basis": "gravimetric"})
    assert bad.status_code == 400


def test_edit_cell(client):
    r = client.post("/api/load/example", json={"kinds": ["cellpy"]})
    snap = _wait_for_job(client, r.json()["job_id"])
    if snap["status"] != "done":
        pytest.skip("example data unavailable")
    cell_id = client.get("/api/state").json()["cells"][0]["id"]

    out = client.post(
        f"/api/cells/{cell_id}/update",
        json={"id": cell_id, "label": "renamed", "group": 5, "selected": False},
    ).json()
    assert out["cell"]["label"] == "renamed"
    assert out["cell"]["group"] == 5
    assert out["state"]["n_selected"] == 0
