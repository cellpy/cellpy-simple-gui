"""Browser upload for served instances (#133).

The sandbox (#120) is right to refuse host paths, but it leaves a browser on
another machine with no way to bring a file in at all. Upload is that way in —
which makes it a place where client-supplied data becomes a filename on our
disk, so most of what follows is about names that are trying to be paths.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cellpy_simple_gui.api.app import create_app
from cellpy_simple_gui.config import get_settings
from cellpy_simple_gui.core import uploads

pytestmark = pytest.mark.essential

TOKEN_HEADER = "X-CSG-Token"


@pytest.fixture()
def served(monkeypatch, tmp_path):
    """A served instance with its data dir under tmp_path."""
    root = tmp_path / "data"
    root.mkdir()
    monkeypatch.setenv("CSG_HOST", "0.0.0.0")
    monkeypatch.setenv("CSG_DATA_DIR", str(root))
    monkeypatch.setenv("CSG_TOKEN", "test-token")
    monkeypatch.delenv("CSG_ALLOW_HOST_PATHS", raising=False)
    get_settings.cache_clear()
    yield root.resolve()
    get_settings.cache_clear()


@pytest.fixture()
def client(served):
    with TestClient(create_app()) as c:
        c.headers.update({TOKEN_HEADER: "test-token"})
        yield c


# --- names that are trying to be paths -------------------------------------- #


@pytest.mark.parametrize(
    ("hostile", "must_not_contain"),
    [
        ("../../../etc/passwd", ".."),
        ("..\\..\\Windows\\win.ini", ".."),
        ("/etc/shadow", "/"),
        (r"C:\Windows\System32\evil.dll", "\\"),
        ("....//....//escape.h5", ".."),
    ],
)
def test_safe_name_reduces_a_path_to_a_filename(hostile, must_not_contain):
    name = uploads.safe_name(hostile)
    assert must_not_contain not in name
    assert name and not name.startswith(".")


@pytest.mark.parametrize("useless", ["", "   ", "/", "..", "...", "///"])
def test_safe_name_refuses_what_is_left_of_nothing(useless):
    with pytest.raises(uploads.UploadRejected):
        uploads.safe_name(useless)


def test_upload_lands_inside_the_data_directory(served, client):
    res = client.post("/api/upload", files={"files": ("cell.h5", b"x" * 32)})
    assert res.status_code == 200, res.text

    saved = res.json()["saved"]
    assert len(saved) == 1
    landed = (served / "uploads" / "cell.h5").resolve()
    assert saved[0]["path"] == str(landed)
    assert landed.is_file() and landed.read_bytes() == b"x" * 32


def test_a_traversing_filename_still_lands_inside(served, client):
    res = client.post(
        "/api/upload", files={"files": ("../../escaped.h5", b"data")}
    )
    assert res.status_code == 200, res.text

    written = Path(res.json()["saved"][0]["path"]).resolve()
    # The only thing that actually matters: wherever it went, it is inside.
    assert written.is_relative_to(served.resolve())
    assert written.parent == (served / "uploads").resolve()
    assert not (served.parent / "escaped.h5").exists()


# --- limits ----------------------------------------------------------------- #


def test_a_file_over_the_cap_is_refused_and_leaves_nothing_behind(served, monkeypatch):
    monkeypatch.setenv("CSG_MAX_UPLOAD_MB", "1")
    get_settings.cache_clear()

    oversized = io.BytesIO(b"x" * (2 * 1024 * 1024))
    with pytest.raises(uploads.UploadRejected, match="larger than"):
        uploads.save(oversized, "big.h5")

    # A partial file would look like a real one to the loader.
    assert list((served / "uploads").glob("*")) == []


def test_an_empty_file_is_refused(served):
    with pytest.raises(uploads.UploadRejected, match="empty"):
        uploads.save(io.BytesIO(b""), "nothing.h5")
    assert list((served / "uploads").glob("*")) == []


def test_one_rejected_file_does_not_lose_the_others(served, client, monkeypatch):
    monkeypatch.setenv("CSG_MAX_UPLOAD_MB", "1")
    get_settings.cache_clear()

    res = client.post(
        "/api/upload",
        files=[
            ("files", ("good.h5", b"fine")),
            ("files", ("huge.h5", b"x" * (2 * 1024 * 1024))),
            ("files", ("also-good.h5", b"fine too")),
        ],
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert [s["name"] for s in body["saved"]] == ["good.h5", "also-good.h5"]
    assert len(body["errors"]) == 1 and "huge.h5" in body["errors"][0]


def test_all_rejected_is_an_error_not_a_silent_nothing(served, client, monkeypatch):
    monkeypatch.setenv("CSG_MAX_UPLOAD_MB", "1")
    get_settings.cache_clear()
    res = client.post(
        "/api/upload", files={"files": ("huge.h5", b"x" * (2 * 1024 * 1024))}
    )
    assert res.status_code == 400
    assert "larger than" in res.json()["detail"]


# --- housekeeping ----------------------------------------------------------- #


def test_two_uploads_of_one_name_are_two_files(served, client):
    for _ in range(2):
        client.post("/api/upload", files={"files": ("same.h5", b"data")})
    names = sorted(p.name for p in (served / "uploads").glob("*"))
    assert names == ["same-1.h5", "same.h5"], names


def test_usage_and_clear(served, client):
    client.post("/api/upload", files={"files": ("a.h5", b"12345")})
    assert client.get("/api/uploads").json()["usage"] == {"files": 1, "bytes": 5}

    cleared = client.request("DELETE", "/api/uploads").json()
    assert cleared == {"removed": 1, "bytes": 5}
    assert client.get("/api/uploads").json()["usage"] == {"files": 0, "bytes": 0}


def test_upload_needs_the_token(served):
    with TestClient(create_app()) as anonymous:
        res = anonymous.post("/api/upload", files={"files": ("a.h5", b"x")})
    assert res.status_code == 401


def test_capabilities_advertise_the_cap(client):
    caps = client.get("/api/system/capabilities").json()
    assert caps["max_upload_mb"] == get_settings().max_upload_mb
    # Served: the UI uses this to lead with upload rather than the path field.
    assert caps["host_paths_allowed"] is False
