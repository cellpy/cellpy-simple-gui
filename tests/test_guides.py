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
