"""The sandbox that stops a served instance reading the host (#120).

Traversal is tested rather than argued: `..`, symlinks, drive letters and UNC
paths all have to be refused, and each of them fails differently.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from cellpy_simple_gui.config import get_settings
from cellpy_simple_gui.core import files, paths

# This is a security boundary, so it belongs in the subset CI actually runs.
# It also matters that CI runs on Linux: the symlink cases below skip on a
# Windows box without symlink privilege, so without this marker they would
# execute nowhere at all.
pytestmark = pytest.mark.essential


@pytest.fixture()
def served(monkeypatch, tmp_path):
    """A served instance whose data dir is ``tmp_path/data``."""
    root = tmp_path / "data"
    root.mkdir()
    monkeypatch.setenv("CSG_HOST", "0.0.0.0")
    monkeypatch.setenv("CSG_DATA_DIR", str(root))
    monkeypatch.delenv("CSG_ALLOW_HOST_PATHS", raising=False)
    get_settings.cache_clear()
    yield root.resolve()
    get_settings.cache_clear()


@pytest.fixture()
def local(monkeypatch, tmp_path):
    """A desktop-style instance on loopback."""
    monkeypatch.setenv("CSG_HOST", "127.0.0.1")
    monkeypatch.setenv("CSG_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("CSG_ALLOW_HOST_PATHS", raising=False)
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


# --- which mode are we in -------------------------------------------------- #


def test_loopback_allows_host_paths(local):
    assert paths.host_paths_allowed() is True
    assert paths.sandbox_root() is None


def test_non_loopback_confines_to_the_data_dir(served):
    assert paths.host_paths_allowed() is False
    assert paths.sandbox_root() == served


def test_override_forces_the_sandbox_on_loopback(local, monkeypatch):
    """The reverse-proxy case: loopback-bound but published to a network."""
    monkeypatch.setenv("CSG_ALLOW_HOST_PATHS", "0")
    get_settings.cache_clear()
    assert paths.host_paths_allowed() is False
    assert paths.sandbox_root() is not None


# --- what gets through ----------------------------------------------------- #


def test_local_mode_passes_host_paths_through(local):
    target = local / "elsewhere" / "cell.cellpy"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"x")
    assert paths.resolve_input(str(target)) == target


def test_served_mode_allows_inside_the_root(served):
    inside = served / "projects" / "p" / "c1.cellpy"
    inside.parent.mkdir(parents=True)
    inside.write_bytes(b"x")
    assert paths.resolve_input(str(inside)) == inside.resolve()


def test_served_mode_treats_relative_as_relative_to_the_root(served):
    (served / "sub").mkdir()
    assert paths.resolve_input("sub") == (served / "sub").resolve()


# --- what does not --------------------------------------------------------- #


def test_served_mode_refuses_a_path_outside(served, tmp_path):
    outside = tmp_path / "secret.txt"
    outside.write_text("nope")
    with pytest.raises(paths.PathNotAllowed):
        paths.resolve_input(str(outside))


def test_served_mode_refuses_dot_dot_traversal(served):
    with pytest.raises(paths.PathNotAllowed):
        paths.resolve_input("../../etc/passwd")
    with pytest.raises(paths.PathNotAllowed):
        paths.resolve_input(str(served / ".." / "secret.txt"))


@pytest.mark.skipif(sys.platform != "win32", reason="Windows path shapes")
def test_served_mode_refuses_drive_and_unc_paths(served):
    for hostile in (r"C:\Windows\win.ini", r"\\somehost\share\file.txt"):
        with pytest.raises(paths.PathNotAllowed):
            paths.resolve_input(hostile)


def test_served_mode_refuses_a_symlink_pointing_out(served, tmp_path):
    """The case string-matching misses: the path looks inside, the target isn't."""
    outside = tmp_path / "outside.txt"
    outside.write_text("nope")
    link = served / "innocent.txt"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks need privileges on this platform")

    with pytest.raises(paths.PathNotAllowed):
        paths.resolve_input(str(link))


def test_served_mode_refuses_empty(served):
    with pytest.raises(paths.PathNotAllowed):
        paths.resolve_input("   ")


# --- globs ----------------------------------------------------------------- #


def test_glob_is_rooted_and_filtered(served, tmp_path):
    (served / "a.cellpy").write_bytes(b"x")
    (served / "b.cellpy").write_bytes(b"x")
    (tmp_path / "outside.cellpy").write_bytes(b"x")

    hits = paths.expand_glob("*.cellpy")
    assert sorted(Path(h).name for h in hits) == ["a.cellpy", "b.cellpy"]

    # An absolute pattern aimed outside matches nothing at all.
    assert paths.expand_glob(str(tmp_path / "*.cellpy")) == []


def test_glob_cannot_climb_out_with_recursive_wildcards(served, tmp_path):
    (tmp_path / "outside.cellpy").write_bytes(b"x")
    assert paths.expand_glob("../**/*.cellpy") == []


def test_glob_drops_symlinked_escapes(served, tmp_path):
    """`**` through a symlinked directory is the classic way out."""
    secret_dir = tmp_path / "secret"
    secret_dir.mkdir()
    (secret_dir / "leak.cellpy").write_bytes(b"x")
    try:
        (served / "link").symlink_to(secret_dir, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks need privileges on this platform")

    assert [h for h in paths.expand_glob("**/*.cellpy") if "leak" in h] == []


# --- the loader that uses all of it ---------------------------------------- #


def test_expand_paths_reports_refusals_instead_of_loading(served, tmp_path):
    outside = tmp_path / "secret.cellpy"
    outside.write_text("nope")
    inside = served / "ok.cellpy"
    inside.write_bytes(b"x")

    exp = files.expand_paths([str(inside), str(outside)])
    assert [Path(p).name for p in exp.paths] == ["ok.cellpy"]
    assert exp.errors and "outside the data directory" in exp.errors[0]


def test_expand_paths_is_unchanged_locally(local, tmp_path):
    target = tmp_path / "anywhere.cellpy"
    target.write_bytes(b"x")
    exp = files.expand_paths([str(target)])
    assert exp.paths == [str(target)] and not exp.errors
