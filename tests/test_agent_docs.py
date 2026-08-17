"""`llms.txt`, `llms-full.txt` and the Claude Skill (#127).

These are the documents nobody re-reads. A human notices a stale README because
they open it; an index written for machines rots in silence, and the failure —
an agent confidently following a link to a guide that was renamed — looks like
the agent being wrong rather than the docs being wrong.

So: both files are generated, this asserts the committed copies match, and it
checks that what the index promises is actually there.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.essential

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "cellpy-app" / "SKILL.md"


@pytest.fixture(scope="module")
def generator():
    path = ROOT / "tools" / "gen_llms_txt.py"
    spec = importlib.util.spec_from_file_location("gen_llms_txt", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["gen_llms_txt"] = module
    spec.loader.exec_module(module)
    return module


# --- generated, therefore checkable ----------------------------------------- #


def test_llms_txt_is_current(generator):
    current = generator.INDEX.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert current == generator.render_index(), (
        "llms.txt is out of date — run: uv run tools/gen_llms_txt.py"
    )


def test_llms_full_txt_is_current(generator):
    current = generator.FULL.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert current == generator.render_full(), (
        "llms-full.txt is out of date — run: uv run tools/gen_llms_txt.py"
    )


def test_every_path_the_index_points_at_exists(generator):
    """A dead link in an index written for machines is silent until it is not."""
    listed = {
        rel for _title, entries in generator.SECTIONS for rel, _note in entries
    }
    listed |= set(generator.FULL_ORDER)
    missing = [rel for rel in listed if not (ROOT / rel).exists()]
    assert not missing, missing


def test_the_index_lists_every_guide(generator):
    """Adding a guide without listing it is the easy mistake; catch it here."""
    index = generator.INDEX.read_text(encoding="utf-8")
    for guide in generator.guide_files():
        assert guide.name in index, f"{guide.name} is not in llms.txt"


def test_llms_full_actually_contains_the_documents(generator):
    """An index is cheap; the concatenation is what an agent will rely on."""
    full = generator.FULL.read_text(encoding="utf-8")
    # Content, not headings: a file listed but empty would pass a heading check.
    assert "def collection_for(" in full          # the starter app
    assert "family.summary_options(hdr)" in full  # guide 3
    assert "CELLPY_<SECTION>__<FIELD>" in full    # guide 5
    assert len(full) > 100_000, len(full)


# --- the skill --------------------------------------------------------------- #


def test_the_skill_has_the_frontmatter_a_skill_needs():
    text = SKILL.read_text(encoding="utf-8")
    frontmatter = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert frontmatter, "SKILL.md must open with YAML frontmatter"

    block = frontmatter.group(1)
    assert re.search(r"^name:\s*cellpy-app\s*$", block, re.MULTILINE)
    assert re.search(r"^description:", block, re.MULTILINE)

    # The description is what decides whether the skill is ever loaded, so it has
    # to name the things a task would mention rather than describe itself.
    for trigger in ("cellpy", "CellpyCell", "collect_", "dQ/dV", "battery"):
        assert trigger in block, f"description does not mention {trigger!r}"


def test_the_skill_states_the_traps_that_produce_plausible_output():
    """The API listing is the cheap half. These are why the skill exists."""
    text = SKILL.read_text(encoding="utf-8")
    for needle in (
        'kind="film"',                 # layout vs kind
        "summary_options",             # availability, judged on the right columns
        "entry_point",                 # menus built from the registry
        "silently drops",              # from_cells
        "get_axes=True",               # cycle_info_plot returns None otherwise
        "max_points",                  # raw_plot payload
        "1.0 mg",                      # the default mass
        "is_grouped",                  # the schema change
    ):
        assert needle in text, f"SKILL.md no longer mentions {needle!r}"


def test_the_skill_reference_is_bundled():
    """Installed elsewhere, the skill has no repo to fall back on."""
    bundled = SKILL.parent / "reference" / "api-reference.md"
    assert bundled.exists()
    assert "reference/api-reference.md" in SKILL.read_text(encoding="utf-8")
