"""Remote folder find via cellpy's filefinder (#162).

No live SFTP: everything goes through the adapter's
``_find_in_raw_file_directory`` seam, and the served/desktop policy is toggled
the same way the #120 / #160 tests do it.
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from cellpy_simple_gui.api.app import create_app
from cellpy_simple_gui.config import get_settings
from cellpy_simple_gui.core import cellpy_adapter
from cellpy_simple_gui.core.library import get_library

DIR = "sftp://user@lab.example/home/user/raw/"


@pytest.fixture()
def local(monkeypatch, tmp_path):
    monkeypatch.setenv("CSG_HOST", "127.0.0.1")
    monkeypatch.setenv("CSG_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("CSG_ALLOW_HOST_PATHS", raising=False)
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


@pytest.fixture()
def served(monkeypatch, tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    monkeypatch.setenv("CSG_HOST", "0.0.0.0")
    monkeypatch.setenv("CSG_DATA_DIR", str(root))
    monkeypatch.delenv("CSG_ALLOW_HOST_PATHS", raising=False)
    get_settings.cache_clear()
    yield root
    get_settings.cache_clear()


@pytest.fixture()
def fake_finder(monkeypatch):
    """Record filefinder calls and answer from a canned listing per extension."""
    calls: list[dict] = []
    listing = {
        "res": [f"{DIR}b_02.res", f"{DIR}a_01.res", f"{DIR}sub/c_03.res"],
        "h5": [f"{DIR}a_01.h5"],
        None: [f"{DIR}a_01.res", f"{DIR}a_01.h5", f"{DIR}notes.txt"],
    }

    def fake(**kwargs):
        calls.append(kwargs)
        return list(listing.get(kwargs.get("extension"), []))

    monkeypatch.setattr(cellpy_adapter, "_find_in_raw_file_directory", fake)
    return calls


# --- adapter ---------------------------------------------------------------- #


def test_find_returns_cellpy_prefixed_uris_sorted(local, fake_finder):
    found = cellpy_adapter.find_remote_files(DIR, extensions=[".res"], max_files=10)
    assert found.errors == []
    assert found.paths == [f"{DIR}a_01.res", f"{DIR}b_02.res", f"{DIR}sub/c_03.res"]
    assert found.total == 3
    assert fake_finder == [
        {"raw_file_dir": DIR, "extension": "res", "glob_txt": None, "allow_error_level": 1}
    ]


def test_find_walks_once_per_extension_and_dedupes(local, fake_finder):
    found = cellpy_adapter.find_remote_files(
        DIR, extensions=[".res", "h5", ".res"], max_files=10
    )
    assert [c["extension"] for c in fake_finder] == ["res", "h5"]
    assert found.total == 4
    assert f"{DIR}a_01.h5" in found.paths


def test_find_without_extensions_lists_everything(local, fake_finder):
    found = cellpy_adapter.find_remote_files(DIR, max_files=10)
    assert fake_finder[0]["extension"] is None
    assert found.total == 3


def test_find_filter_bare_text_means_contains(local, fake_finder):
    cellpy_adapter.find_remote_files(DIR, extensions=[".res"], filter_text=" a_0 ", max_files=10)
    assert fake_finder[0]["glob_txt"] == "*a_0*"


def test_find_filter_glob_passes_through(local, fake_finder):
    cellpy_adapter.find_remote_files(DIR, extensions=[".res"], filter_text="2016*_cc_??", max_files=10)
    assert fake_finder[0]["glob_txt"] == "2016*_cc_??"


def test_find_caps_at_max_files_and_says_so(local, fake_finder):
    found = cellpy_adapter.find_remote_files(DIR, extensions=[".res"], max_files=2)
    assert found.total == 3
    assert found.paths == [f"{DIR}a_01.res", f"{DIR}b_02.res"]
    assert len(found.notes) == 1
    assert "Found 3 files; keeping the first 2" in found.notes[0]


def test_find_warns_about_huge_listings(local, monkeypatch):
    many = [f"{DIR}f{i:05d}.res" for i in range(cellpy_adapter.LARGE_REMOTE_FIND)]
    monkeypatch.setattr(cellpy_adapter, "_find_in_raw_file_directory", lambda **kw: many)
    found = cellpy_adapter.find_remote_files(DIR, extensions=[".res"], max_files=10)
    assert found.total == cellpy_adapter.LARGE_REMOTE_FIND
    assert any("project-scoped" in n for n in found.notes)


def test_find_reports_nothing_found_as_an_error(local, fake_finder):
    found = cellpy_adapter.find_remote_files(DIR, extensions=[".mpr"], max_files=10)
    assert found.paths == []
    assert found.errors == [f"No files found in {DIR} (*.mpr)."]


def test_find_surfaces_search_failures(local, monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("Authentication failed.")

    monkeypatch.setattr(cellpy_adapter, "_find_in_raw_file_directory", boom)
    found = cellpy_adapter.find_remote_files(DIR, extensions=[".res"], max_files=10)
    assert found.paths == []
    assert len(found.errors) == 1
    assert "Authentication failed" in found.errors[0]
    assert "*.res" in found.errors[0]


def test_find_refuses_local_directories_without_touching_cellpy(local, fake_finder, tmp_path):
    found = cellpy_adapter.find_remote_files(str(tmp_path), extensions=[".res"], max_files=10)
    assert fake_finder == []
    assert found.paths == []
    assert "Not a remote folder" in found.errors[0]
    assert "glob" in found.errors[0]


def test_find_refuses_when_served(served, fake_finder):
    found = cellpy_adapter.find_remote_files(DIR, extensions=[".res"], max_files=10)
    assert fake_finder == []
    assert found.paths == []
    assert "desktop-only" in found.errors[0]


def test_find_empty_directory_is_an_error(local, fake_finder):
    found = cellpy_adapter.find_remote_files("  ", max_files=10)
    assert found.errors == ["Remote folder is empty."]
    assert fake_finder == []


# --- API -------------------------------------------------------------------- #


def _client():
    get_library().clear()
    c = TestClient(create_app())
    c.headers.update({"X-CSG-Token": get_settings().token})
    return c


def _wait(client, job_id, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        snap = client.get(f"/api/jobs/{job_id}").json()
        if snap["status"] in ("done", "error", "cancelled"):
            return snap
        time.sleep(0.05)
    raise AssertionError("job did not finish in time")


def test_remote_find_endpoint_runs_as_a_job(local, fake_finder):
    client = _client()
    r = client.post(
        "/api/remote/find",
        json={"directory": DIR, "extensions": [".res"], "filter": "a_0", "max_files": 5},
    )
    assert r.status_code == 200
    snap = _wait(client, r.json()["job_id"])
    assert snap["status"] == "done"
    result = snap["result"]
    assert result["paths"] == [f"{DIR}a_01.res", f"{DIR}b_02.res", f"{DIR}sub/c_03.res"]
    assert result["total"] == 3
    assert result["errors"] == []
    assert fake_finder[0]["glob_txt"] == "*a_0*"


def test_remote_find_endpoint_enforces_the_max_files_ceiling(local, fake_finder):
    client = _client()
    ceiling = get_settings().max_files
    r = client.post(
        "/api/remote/find",
        json={"directory": DIR, "extensions": [".res"], "max_files": ceiling + 1000},
    )
    snap = _wait(client, r.json()["job_id"])
    assert len(snap["result"]["paths"]) <= ceiling


def test_remote_find_endpoint_reports_served_refusal_in_errors(served, fake_finder):
    client = _client()
    r = client.post("/api/remote/find", json={"directory": DIR, "extensions": [".res"]})
    assert r.status_code == 200
    snap = _wait(client, r.json()["job_id"])
    assert snap["status"] == "done"
    assert snap["result"]["paths"] == []
    assert "desktop-only" in snap["result"]["errors"][0]
    assert fake_finder == []


def test_remote_find_endpoint_rejects_empty_directory(local):
    client = _client()
    assert client.post("/api/remote/find", json={"directory": "   "}).status_code == 400


def test_remote_find_endpoint_needs_the_token(local):
    c = TestClient(create_app())
    assert c.post("/api/remote/find", json={"directory": DIR}).status_code in (401, 403)
