# Guides: what belongs upstream in cellpy

Written 2026-08-17 alongside `docs/guides/` (issue #126). The decision taken at
the start of that issue was **write the guides here first, then propose the
cellpy-general parts upstream** — rather than splitting up front, which would
have meant deciding what was general before knowing what the guides said.

This file is the concrete follow-up list, so "propose it upstream" is a task
rather than an intention.

## Why not upstream first

Two reasons, both practical.

The guides are **verified by a test runner** (`tests/test_guides.py` executes
every ```python block). That harness lives here, and moving the prose without it
would move exactly the property that makes the guides trustworthy. Anything
extracted upstream should carry an equivalent, or it will drift the way the docs
it replaces did.

And #127 (the machine-readable layer) needs a **local source of truth** to
distil. Blocking it on a cellpy merge would invert the dependency.

## Candidates, by strength

### Strong — general cellpy knowledge, no app in it

| Guide | Section | Why it belongs upstream |
|---|---|---|
| 2 | The four collectors and what a `Collection` is | This is the library's own vocabulary; every consumer needs it and there is currently no one page that says it |
| 2 | Grouping changes the *schema*, not just the values (`cell` → `variable`/`mean`/`std`) | Surprising, universal, and cheap to state |
| 2 | polars here, pandas there — the boundary table | Comes up for everyone; §7 was filed about exactly this |
| 3 | `family.summary_options(hdr)` as the way to collect a registry family | The accessor exists *because* an app asked for it (#868); it deserves a documented usage, not just an API entry |
| 3 | Asked-for columns vs drawn columns (`summary_options().columns` vs `columns()`) | The distinction that caused cellpy-simple-gui#106; anyone building a plot menu will hit it |
| 3 | `cycle_info_plot` needs `get_axes=True` to return a figure | Pure API surprise, one sentence, currently undocumented |
| 5 | The five config layers, `sources()` provenance, `active_config_file()` | The 2.1.2 config stack is a large improvement that is under-documented; this is its missing user guide |
| 5 | `CELLPY_<SECTION>__<FIELD>` as the deployment path | Nothing else documents configuring cellpy without a file |
| 6 | `override()` is per thread/task, `reload()` and `set_load_options()` are process-global | Directly from #850; the fix landed, the guidance did not |

### Medium — general, but shaped by a decision an app has to make

| Guide | Section | Note |
|---|---|---|
| 1 | Discovered ≠ usable (the `mdb-export` / `libodbc` probes) | Already raised as cellpy#938. If that lands, this becomes "call the new API" and shrinks |
| 3 | Layouts vs kinds and the `film` trap | Upstream-worthy *as documentation of `kind=`*, which `Collection.plot`'s docstring omits. The workaround half goes away when #874 closes |
| 4 | kaleido installed ≠ figure export works | True of plotly generally, not only cellpy — but cellpy is where a battery person meets it |
| 5 | The relative-path / import-time `examplesdir` trap | Raised on cellpy#938. If the default becomes absolute, most of this section deletes itself |

### Stays here — about building an app, not about cellpy

Guide 7 in full (the delegation inventory is this project's own record), the
worker-pool code in guide 6, the sandboxing note, the cell-library and project
sections, and every "what we did instead" paragraph. Upstream should not carry
one downstream app's architecture.

## Suggested shape of the proposal

One issue on cellpy, not nine: *"documentation: a task-shaped guide set for
people building on cellpy"*, linking to `docs/guides/` as a working draft and
offering the strong-list sections as a PR. Filing nine separate documentation
issues would be noise, and the value is in the set having one voice.

Two things to say explicitly in it:

1. The prose is offered, not imposed — cellpy's docs have their own toolchain and
   register.
2. The executable-block harness is the part worth copying regardless of whether
   the prose is. It is ~60 lines and it is why these examples are correct.

## New finding to file separately

§34 in `CELLPY_PAINPOINTS.md` — `from_cells` silently drops values that are not
cells (a path, an `int`, anything) with no exception, warning or log line. Found
*by writing the guides*, which is a small argument for documentation with a test
runner attached. Not yet filed; it is a normal issue rather than a docs one.
