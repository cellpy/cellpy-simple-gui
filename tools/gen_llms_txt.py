"""Generate `llms.txt` and `llms-full.txt` (#127).

Half the audience for the guides is coding agents, which want the same knowledge
in a different shape: an index they can fetch selectively, and one file they can
swallow whole.

Both are generated from the documents themselves — the guide titles and
one-liners are read out of the guides — so an index that lists a guide that no
longer exists, or describes it wrongly, is not a thing that can happen quietly.

    uv run tools/gen_llms_txt.py            # rewrite both files
    uv run tools/gen_llms_txt.py --check    # exit 1 if either is out of date

See https://llmstxt.org for the convention.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "llms.txt"
FULL = ROOT / "llms-full.txt"

RAW = "https://raw.githubusercontent.com/cellpy/cellpy-simple-gui/main"

SUMMARY = (
    "A desktop and self-hosted GUI for exploring battery cell data with cellpy, "
    "plus the documentation for building your own cellpy application."
)

CONTEXT = """\
Two audiences share these documents. Everything under `docs/guides/` is
organised by what someone is trying to do rather than by module, and every
Python block in those guides is executed in CI, so the code in them works
against the cellpy version they are written for (2.1.3).

If you are writing code that uses cellpy, the shortest useful path is:
`docs/api-reference.md` for the calls, `examples/starter/app.py` for a working
program to imitate, and the relevant guide for the traps. The traps are the
point — most of what goes wrong with cellpy produces plausible output rather
than an error.
"""

#: (section title, [(path, note)]). Paths are repo-relative; the note is written
#: here only where a document cannot describe itself.
SECTIONS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "Start here",
        [
            ("docs/api-reference.md", "The 44 cellpy calls that matter, with real signatures introspected from the installed package and one line each of what the signature cannot tell you."),
            ("examples/starter/app.py", "A complete cellpy application in one file: load cells, build a Collection, plot, export. ~340 lines, PEP 723 header, runs with `uv run --script`."),
            ("examples/starter/README.md", "What the starter does and does not do, and how to add a plot type."),
        ],
    ),
    ("Guides", []),  # filled from the guide files themselves
    (
        "Project documentation",
        [
            ("README.md", "What the application is, how to install and run it, and how it is built."),
            ("docs/deployment.md", "Running it as a server: container image, the token, what to put in front of it."),
            ("docs/windows-installer.md", "Building and shipping the Windows installer."),
            ("docs/releasing.md", "The release pipeline: PyPI, GHCR, GitHub Releases."),
        ],
    ),
    (
        "Optional",
        [
            ("CELLPY_PAINPOINTS.md", "Every rough edge found while building on cellpy, with the upstream issue that closed it. Read this before working around something — it may already be fixed."),
            ("docs/issue-workflow.md", "How work is tracked in this repository."),
        ],
    ),
]

#: Concatenated into llms-full.txt, in reading order.
FULL_ORDER = [
    "README.md",
    "docs/guides/README.md",
    "docs/guides/01-loading-cells.md",
    "docs/guides/02-collections.md",
    "docs/guides/03-plotting.md",
    "docs/guides/04-exporting.md",
    "docs/guides/05-configuration.md",
    "docs/guides/06-state-and-threading.md",
    "docs/guides/07-delegation.md",
    "docs/api-reference.md",
    "examples/starter/README.md",
    "examples/starter/app.py",
]


def guide_files() -> list[Path]:
    return sorted((ROOT / "docs" / "guides").glob("[0-9]*.md"))


def describe_guide(path: Path) -> tuple[str, str]:
    """`(title, one-liner)` read out of the guide itself.

    The guides open with `# 3. Plotting a collection` followed by an italic
    `*You have a Collection. You want …*`, which is exactly the pair an index
    wants. Reading it rather than restating it means the index cannot describe a
    guide that has since changed its mind.
    """
    text = path.read_text(encoding="utf-8")
    title = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    # The intent line is allowed to wrap, so match across newlines and collapse.
    intent = re.search(r"^\*([^*].*?)\*\s*$", text, re.MULTILINE | re.DOTALL)
    if not title or not intent:
        raise ValueError(
            f"{path.name} needs an '# H1' and an italic '*You ...*' line; "
            "the llms.txt index is built from them"
        )
    return title.group(1).strip(), " ".join(intent.group(1).split())


def render_index() -> str:
    lines = [
        "# cellpy-simple-gui",
        "",
        f"> {SUMMARY}",
        "",
        CONTEXT.rstrip(),
        "",
    ]
    for title, entries in SECTIONS:
        lines += [f"## {title}", ""]
        if title == "Guides":
            lines.append(
                "Task-shaped. Every Python block in these is executed by CI."
            )
            lines.append("")
            for guide in guide_files():
                name, intent = describe_guide(guide)
                rel = guide.relative_to(ROOT).as_posix()
                lines.append(f"- [{name}]({RAW}/{rel}): {intent}")
        else:
            for rel, note in entries:
                lines.append(f"- [{rel}]({RAW}/{rel}): {note}")
        lines.append("")
    lines += [
        "## Everything at once",
        "",
        f"- [llms-full.txt]({RAW}/llms-full.txt): the guides, the API reference and "
        "the starter app concatenated, for a single fetch.",
        "",
    ]
    return "\n".join(lines)


def render_full() -> str:
    parts = [
        "# cellpy-simple-gui — full documentation",
        "",
        f"> {SUMMARY}",
        "",
        "Concatenated from the repository. Each document is preceded by its path.",
        "Generated by tools/gen_llms_txt.py — do not edit.",
        "",
    ]
    for rel in FULL_ORDER:
        path = ROOT / rel
        if not path.exists():
            raise FileNotFoundError(f"llms-full.txt lists a missing file: {rel}")
        fence = "```python" if path.suffix == ".py" else ""
        parts += ["", "=" * 78, f"FILE: {rel}", "=" * 78, ""]
        if fence:
            parts += [fence, path.read_text(encoding="utf-8").rstrip(), "```"]
        else:
            parts.append(path.read_text(encoding="utf-8").rstrip())
    parts.append("")
    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 if out of date")
    args = parser.parse_args()

    wanted = {INDEX: render_index(), FULL: render_full()}
    if args.check:
        stale = [
            p.name
            for p, text in wanted.items()
            if not p.exists()
            or p.read_text(encoding="utf-8").replace("\r\n", "\n") != text
        ]
        if stale:
            print(f"out of date: {', '.join(stale)} — run: uv run tools/gen_llms_txt.py")
            return 1
        print("llms.txt and llms-full.txt are up to date")
        return 0

    for path, text in wanted.items():
        path.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {path.name} ({len(text.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
