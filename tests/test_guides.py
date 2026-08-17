"""Run the code in `docs/guides/` (#126).

A guide whose examples do not work is worse than no guide: it costs the reader
the time they spent trusting it. So every ```python block in every guide is
executed here, in document order, in one namespace per guide — which makes the
guides copy-pasteable from the top by construction rather than by care.

```pycon blocks are REPL transcripts, usually of something going *wrong*, and are
deliberately not run.

When one of these fails it is normally the guide that is out of date, not the
test. Fix the prose.
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path

import pytest

pytestmark = pytest.mark.essential

GUIDES = sorted((Path(__file__).resolve().parents[1] / "docs" / "guides").glob("*.md"))

#: cellpy release that fixed the `layout="film"` trap (cellpy#874).
FILM_FIXED_IN = (2, 1, 3)

#: Opening fence, its info string, the body. Only ``python`` is executed — the
#: language is the contract, so a block that cannot run is marked by fencing it
#: as ``pycon`` rather than by a comment the runner would have to parse.
_BLOCK = re.compile(r"^```([^\n`]*)\n(.*?)^```", re.DOTALL | re.MULTILINE)


def python_blocks(markdown: str) -> list[str]:
    return [
        body
        for info, body in _BLOCK.findall(markdown)
        if info.strip() == "python"
    ]


def test_there_are_guides_to_run():
    """A glob that silently matches nothing is the classic way to pass by doing nothing."""
    assert len(GUIDES) >= 8, [g.name for g in GUIDES]  # seven guides + the index


def test_the_upstream_bugs_the_guides_describe_are_still_bugs():
    """Claims about broken upstream behaviour need checking too.

    This was found the hard way. The guides' ```pycon blocks are transcripts of
    things going *wrong*, which is exactly why they are not executed — and that
    made them the one place a claim could quietly go stale. cellpy 2.1.3 fixed
    the `layout="film"` trap while guide 3 still presented it as open, and no
    test noticed, because the stale claim was in the block type CI skips.

    So the *behaviour* is asserted here even though the transcript is not run: if
    an upstream fix lands, this fails and the prose gets corrected rather than
    quietly misleading someone.
    """
    from importlib.metadata import version

    from cellpy.plotting.collected import resolve_collected_layout_kind as resolve

    installed = tuple(int(p) for p in version("cellpy").split(".")[:3] if p.isdigit())
    guide = (GUIDES[0].parent / "03-plotting.md").read_text(encoding="utf-8")

    # True on every version, which is why the guides tell you to write this.
    assert resolve(kind="film")[1] == "film"

    if installed >= FILM_FIXED_IN:
        assert resolve(layout="film")[1] == "film", "guide 3 says 2.1.3+ accepts it"
        with pytest.raises(ValueError):
            resolve(layout="totally_bogus")
    else:
        # Still broken here, so the guide is right to warn about it.
        assert resolve(layout="film")[1] == "line"
        assert resolve(layout="totally_bogus")[1] == "line"
        assert "On 2.1.2 and earlier" in guide


@pytest.mark.parametrize("guide", GUIDES, ids=lambda p: p.stem)
def test_the_code_in_this_guide_runs(guide, example_cell, monkeypatch):
    blocks = python_blocks(guide.read_text(encoding="utf-8"))
    if not blocks:
        pytest.skip(f"{guide.name} has no runnable blocks")

    # The guides load the demo cell the way a reader would. Handing back the
    # session fixture keeps that honest and keeps the suite from re-reading an
    # 8 MB HDF5 file once per guide.
    from cellpy.utils import example_data

    monkeypatch.setattr(example_data, "cellpy_file", lambda *a, **k: example_cell)

    namespace: dict = {"__name__": "__guide__"}
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for n, block in enumerate(blocks, start=1):
                try:
                    exec(compile(block, f"{guide.name}#block{n}", "exec"), namespace)
                except Exception as exc:
                    raise AssertionError(
                        f"{guide.name} block {n} failed: {type(exc).__name__}: {exc}\n"
                        f"--- block ---\n{block}"
                    ) from exc
    finally:
        # The configuration guide demonstrates `config.reload(...)`, which is
        # process-global on purpose — so a guide can leave cellpy configured for
        # everything that runs after it. Put it back.
        from cellpy import config

        config.reload()
