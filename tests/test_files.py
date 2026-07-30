"""Tests for glob/path expansion."""

from __future__ import annotations

import pytest

from cellpy_simple_gui.core.files import expand_paths


@pytest.mark.essential
def test_literal_missing(tmp_path):
    exp = expand_paths([str(tmp_path / "nope.h5")])
    assert exp.paths == []
    assert exp.errors and "Not found" in exp.errors[0]


@pytest.mark.essential
def test_literal_found(tmp_path):
    f = tmp_path / "a.cellpy"
    f.write_text("x")
    exp = expand_paths([str(f)])
    assert exp.paths == [str(f)]
    assert not exp.errors


@pytest.mark.essential
def test_glob_no_match(tmp_path):
    exp = expand_paths([str(tmp_path / "*.h5")])
    assert exp.paths == []
    assert exp.errors and "No files matched" in exp.errors[0]


def test_glob_match_and_cap(tmp_path):
    for i in range(5):
        (tmp_path / f"cell_{i}.cellpy").write_text("x")
    exp = expand_paths([str(tmp_path / "*.cellpy")], max_files=3)
    assert len(exp.paths) == 3
    assert exp.notes and "loaded the first 3" in exp.notes[0]


def test_dedup(tmp_path):
    f = tmp_path / "a.cellpy"
    f.write_text("x")
    exp = expand_paths([str(f), str(tmp_path / "*.cellpy")])
    assert exp.paths == [str(f)]
