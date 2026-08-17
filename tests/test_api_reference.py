"""Keep `docs/api-reference.md` honest (#127).

The reference exists so an agent does not have to grep `site-packages`. That is
only worth anything if it describes the cellpy that is actually installed — a
reference quoting a signature from two releases ago is worse than none, because
it is confidently wrong.

So the signatures are generated, and this asserts the committed file is what the
generator produces right now. A cellpy upgrade that changes a signature fails
here until someone regenerates.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from importlib.metadata import version
from pathlib import Path

import pytest

pytestmark = pytest.mark.essential

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "tools" / "gen_api_reference.py"
REFERENCE = ROOT / "docs" / "api-reference.md"


def generated_against() -> str:
    """The cellpy version the committed reference was generated from."""
    match = re.search(
        r"Generated from the installed \*\*cellpy ([^*]+)\*\*",
        REFERENCE.read_text(encoding="utf-8"),
    )
    assert match, "the reference no longer states which cellpy it came from"
    return match.group(1).strip()


def skip_unless_pinned_cellpy():
    """Only the locked environment can hold the reference to the byte.

    CI deliberately runs a second job with a floating resolution to catch future
    breakage, and that job may install a newer cellpy than the one this file was
    generated from — at which point the file is not *wrong*, it is describing a
    different release. Failing there would train people to regenerate against
    whatever CI happened to resolve, which is how a reference ends up describing
    a version nobody runs.

    `test_every_listed_call_actually_exists` still runs on every version, so a
    call disappearing upstream is caught either way.
    """
    installed, documented = version("cellpy"), generated_against()
    if installed != documented:
        pytest.skip(
            f"reference documents cellpy {documented}, this environment has "
            f"{installed} — exact match is only enforced on the pinned version"
        )


@pytest.fixture(scope="module")
def generator():
    spec = importlib.util.spec_from_file_location("gen_api_reference", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    sys.modules["gen_api_reference"] = module
    spec.loader.exec_module(module)
    return module


def test_the_committed_reference_matches_the_installed_cellpy(generator):
    skip_unless_pinned_cellpy()
    current = REFERENCE.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert current == generator.render(), (
        "docs/api-reference.md is out of date — run:\n"
        "    uv run tools/gen_api_reference.py"
    )


def test_the_reference_does_not_depend_on_which_python_generated_it():
    """`inspect.signature` renders some types differently per interpreter.

    Found by CI: the same cellpy produced `Optional[str]` / `pathlib._local.Path`
    on 3.13 and `str | None` / `pathlib.Path` on 3.14, so the two jobs could not
    both pass — a diff that says nothing about cellpy and fails anyway. The
    generator normalises to the modern spelling; this stops the old forms
    creeping back in.

    `pathlib._local` is private besides, and had no business in a reference.
    """
    text = REFERENCE.read_text(encoding="utf-8")
    for interpreter_artifact in ("pathlib._local", "Optional[", "Union["):
        assert interpreter_artifact not in text, interpreter_artifact


def test_the_reference_and_the_skill_copy_are_byte_identical():
    """Independent of any cellpy version: two committed files, same bytes.

    This is the half of the guarantee that must not depend on which environment
    the tests run in — if the two copies drift, one of them is lying whatever
    cellpy is installed.
    """
    copy = ROOT / "skills" / "cellpy-app" / "reference" / "api-reference.md"
    assert copy.exists(), f"{copy} missing — run: uv run tools/gen_api_reference.py"
    assert copy.read_bytes() == REFERENCE.read_bytes()


def test_the_skill_carries_the_same_reference(generator):
    skip_unless_pinned_cellpy()
    """The skill bundles its own copy so it works away from this repo.

    Two copies is two chances to be wrong, which is why both are written by one
    run of the generator and compared here rather than trusted.
    """
    copy = generator.SKILL_COPY
    assert copy.exists(), f"{copy} missing — run: uv run tools/gen_api_reference.py"
    assert copy.read_text(encoding="utf-8").replace("\r\n", "\n") == generator.render()


def test_every_listed_call_actually_exists(generator):
    """The curated list is hand-written; a typo in it would ship a dead entry."""
    for _title, _blurb, entries in generator.SECTIONS:
        for path, _semantics in entries:
            generator.resolve(path)  # raises if it does not exist


def test_it_covers_the_calls_the_guides_lean_on(generator):
    """The reference and the guides must not drift apart.

    Not a count — a count passes while the *wrong* forty calls are listed. These
    are the ones a reader who followed the guides will come here looking for, and
    the ones whose absence sent us reading cellpy source in the first place.
    """
    listed = {
        path for _t, _b, entries in generator.SECTIONS for path, _s in entries
    }
    must_have = {
        "cellpy.get",
        "cellpy.collect.from_cells",
        "cellpy.collect.collect_summaries",
        "cellpy.collect.collect_ica",
        "cellpy.collect.collect_dva",
        "cellpy.collect.collection.Collection.plot",
        "cellpy.plotting.registry.families",
        "cellpy.plotting.registry.PlotFamily.summary_options",
        "cellpy.plotting.figures.write_image",
        "cellpy.config.override",
        "cellpy.config.sources",
        "cellpy.utils.plotutils.raw_plot",
    }
    assert must_have <= listed, sorted(must_have - listed)
    assert len(listed) >= 40, f"only {len(listed)} calls listed"


def test_the_sharp_edges_are_stated_where_someone_will_read_them(generator):
    """A signature cannot say `get_axes=True` is required. The prose has to.

    Each of these cost this project real time to discover, and each is invisible
    from the signature alone — which is the entire justification for a curated
    reference over generated API docs.
    """
    semantics = {
        path: text for _t, _b, entries in generator.SECTIONS for path, text in entries
    }
    expected = {
        "cellpy.utils.plotutils.cycle_info_plot": "get_axes=True",
        "cellpy.utils.plotutils.raw_plot": "max_points",
        "cellpy.plotting.registry.families": "entry_point",
        "cellpy.collect.from_cells": "silently",
        "cellpy.config.override": "per thread",
        "cellpy.config.reload": "Process-global",
        "cellpy.utils.example_data.rate_file": "not a cell",
        "cellpy.read_meta": "cellpy files only",
    }
    for path, needle in expected.items():
        assert needle in semantics[path], f"{path} no longer mentions {needle!r}"
