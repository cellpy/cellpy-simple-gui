# An MCP server for cellpy — design, and what a prototype found

Written 2026-08-17 for [#128](https://github.com/cellpy/cellpy-simple-gui/issues/128),
against **cellpy 2.1.2** and the **mcp 2.0.0** Python SDK. Scoped deliberately:
design and prototype, not ship.

The prototype is [`examples/mcp/server.py`](../../examples/mcp/server.py) —
eight tools, driven end to end over the real MCP protocol. Everything below that
sounds like an opinion was measured.

**This document has two rounds.** Everything down to *Reproducing* is the
original pass. [Round two](#round-two-four-user-groups-not-one) — written
2026-09-05 against cellpy 2.1.3, after #840 came back asking for three more
audiences, a local launcher, and help with the API docs — adds four tools, three
prompts, two findings, and supersedes the closing sections.

## Why an MCP server at all

The other artifacts from this phase hand an agent *documentation* and let it
write code. An MCP server hands it *cellpy* and lets it call things. The
[cold-context test](agent-docs-test.md) is the evidence for how much that is
worth: with good docs, an agent got a dQ/dV density film right on the first run
and needed no experimentation. That is the ceiling for docs, and it is high.

So the case for a server is not "agents cannot use cellpy" — they can. It is:

- **No environment.** Nothing to install, no dependency resolution, no Python
  version. A large share of what goes wrong for an agent is setup.
- **The traps become unreachable rather than documented.** `direction` defaults
  to charge; `kind="film"` is not `layout="film"`; a missing column draws an
  empty chart. A tool can *report* all three in its result instead of hoping
  someone read the guide.
- **Payloads stay bounded by construction.** An agent writing code decides for
  itself whether to print a 300-row frame. A tool decides for it.

And the case against, which is real: it is a **long-lived process holding other
people's data**, which is a maintenance and security commitment the docs are not.

## Tool surface

Eight tools proved sufficient for the whole arc — load, inspect, collect,
render, export.

| Tool | Returns |
|---|---|
| `list_instruments` | loader ids, suffixes, and **whether each can run here** |
| `load_cell(path, instrument, mass_mg)` | a handle, cycle count, mass, and the summary column *names* |
| `list_cells` | handles loaded in this process |
| `describe_plot_families` | the 20 summary families, each marked available or with the columns it lacks |
| `collect(kind, …)` | a handle, row count, column names, `is_grouped`, and direction counts for ICA/DVA |
| `preview_collection(handle, rows)` | a few rows, hard-capped |
| `render(handle, path, kind, …)` | a written figure file, plus **trace types and points plotted** |
| `export_collection(handle, path)` | a written data file, plus rows and bytes |

Three properties matter more than the list.

**Handles, not data.** Only `preview_collection` returns rows, and it caps at 20
whatever is asked. One collected summary is ~29 kB of CSV and a raw figure can be
7 MB; a tool result goes into a context window, so returning frames is how you
burn one. Measured on the demo cell: the whole eight-call session above put a few
kilobytes in front of the model and wrote 70 kB of figure and 29 kB of CSV to
disk.

**Results carry the trap.** `render` returns `trace_types` and
`points_plotted` beside `rows_collected`. An agent asking for a film sees
`['histogram2d']` and knows it did not get lines; an agent that forgot
`direction="both"` sees 891 of 2328 and can notice. This is the docs' hardest
job — the failures are *plausible* — done as data instead of prose.

**Availability is answered, not guessed.** `describe_plot_families` judges on
`summary_options().columns`, so it reports 15 of 20 available on the demo cell
and names the missing columns for the rest, rather than letting the agent
discover it by drawing an empty chart.

## Hard part 1 — state

**Finding: mcp 2.0 does not give a tool a stable session identity.**

The intended design was a per-session store. The SDK looks like it supports it —
the tool `Context` has a `session`. Measured across three calls on one client
connection:

```
{'session_type': 'ServerSession', 'session_id': 2424878659088, 'request_id': '2'}
{'session_type': 'ServerSession', 'session_id': 2424878899296, 'request_id': '4'}
{'session_type': 'ServerSession', 'session_id': 2424878897168, 'request_id': '5'}
distinct session objects across 3 calls: 3
```

A `WeakKeyDictionary` keyed on `ctx.session` therefore hands every call a fresh,
empty state — and **fails silently**: the server does not error, it forgets the
cell you loaded and then says "load a cell first". That is exactly how the first
version of the prototype behaved.

There is a second `Context` class, `mcp.server.context.Context`, which *does*
have a `session_id` — and is not the one injected into tools. (The one that is,
`mcp.server.mcpserver.Context`, is also the only one `@server.tool()` accepts:
annotate with the other and registration fails with a pydantic schema error
naming neither the import nor the fix.)

**Conclusion.** Under **stdio** — how MCP servers are normally launched — each
client spawns its own process, so process isolation *is* session isolation and
no keying is needed. The prototype does that, with a comment saying so. A shared
**streamable-http** deployment would need a session token passed in the tool
arguments, or one process per client anyway.

That makes cellpy's process-global configuration a much smaller problem than
#128 anticipated: with one client per process there is no cross-talk to create.
The rule that survives is narrower and still worth stating:

> **A tool must never call `config.reload()` or `set_load_options()`.** Both are
> process-global. `config.override()` is contextvar-scoped and is the only safe
> way to vary settings for one call.

The app's `activate_project_config` — a module global calling `reload()` — is
correct for a desktop app where a project switch *is* process-wide, and would be
wrong here. Same code, different deployment, opposite verdict.

## Hard part 2 — file access

This is #120 in a different costume, and the costume is worse: the caller is a
language model acting on text it may have read in a file. A desktop user typing
a path is exercising judgement; an agent following an instruction is not.

The prototype reuses the answer this project already has, with one addition from
[#152](https://github.com/cellpy/cellpy-simple-gui/pull/152): settle the volume
from the string before any filesystem call, so a UNC path never sends Windows
looking for a host, and the boundary never depends on what a name server says.

Verified refusals, over the protocol:

| Input | Result |
|---|---|
| `../escape.cellpy` | outside the data directory |
| `C:/Windows/win.ini` | outside the data directory |
| `\\somehost\share\x.cellpy` | outside the data directory (no network lookup) |
| `/etc/passwd` | outside the data directory |
| `nope.cellpy` | does not exist |
| export to `out/x.exe` | write a .csv, .parquet or .json file |

Two design points beyond the check itself:

- **No default root of `/`.** `CELLPY_MCP_ROOT` defaults to `~/cellpy_mcp`, not
  the filesystem. A server that starts wide open and relies on being configured
  is a server that ships wide open.
- **Writes are sandboxed too, and extension-checked.** `render` and
  `export_collection` take a path, so they are a write primitive; unchecked, the
  read sandbox would be decoration.

Not addressed, and it would need to be before anything ships: an agent can still
fill the sandbox with figures. A quota, or a temp directory that is cleaned,
belongs in a real version.

## What the prototype does not answer

- **Concurrency.** Tools are synchronous and cellpy is not thread-safe in any
  documented way. One client per process makes this moot for stdio; http does
  not.
- **Large files.** `load_cell` blocks. There is no progress and no cancellation,
  because cellpy offers neither ([guide 6](../../docs/guides/06-state-and-threading.md)).
  An agent waiting 40 seconds with no signal is a bad experience and an MCP
  client may time out.
- **Memory.** Cells stay loaded until the process ends. No eviction.
- **The SDK is young.** mcp 2.0 renamed `FastMCP` to `MCPServer` and has two
  `Context` classes with different attributes. Anything built now will move.

## Recommendation

**Worth doing, and worth doing small.** The tool surface above is nearly the
whole useful API, the two hard parts turned out to be tractable, and stdio makes
the multi-client problem disappear rather than needing solving.

But **not in cellpy itself, yet**. The SDK is moving, the security surface is a
real commitment, and the natural home is a separate package (`cellpy-mcp`) that
depends on cellpy — which also means it can move at the SDK's pace rather than
cellpy's release cadence. If it proves itself there, absorbing it later is easy;
extracting it from cellpy after the fact is not.

The prototype is small enough to be a starting point for that package or to be
thrown away, which is what a prototype is for.

## Proposed upstream

Posted to [cellpy#840](https://github.com/jepegit/cellpy/issues/840#issuecomment-5314927631)
on 2026-08-17 — the tool surface, both findings, and the recommendation above,
offered rather than prescribed. #840 was an empty placeholder ("MCP integration
— any thoughts?") with a v2.3 milestone, so a concrete starting point was the
useful thing to contribute.

## Reproducing

```bash
CELLPY_MCP_ROOT=/some/data uv run --script examples/mcp/server.py
```

`tests/test_mcp_prototype.py` drives it over the protocol with an in-process
client. It skips when `mcp` is not installed — install with
`uv sync --extra mcp`.

## Round two: four user groups, not one

The first pass built for one caller — someone with an agent, automating cell
handling or building on cellpy. #840 came back with three more, and they change
the design more than the tool list suggests:

| Who | What they want | What it needs |
|---|---|---|
| **Builders** | a GUI, a batch script | the eight data tools, plus real signatures |
| **Chat users** | "plot these cells for me" | prompts, and an install that is not a JSON edit |
| **Terminal-avoiders** | `cellpy new` without a terminal | templating as a tool |
| **Everyone** | "what does this argument do?" | the API, introspected from the installed package |

The fourth is the one worth taking seriously, because it is not a feature
request. It is the observation that **people do not read API documentation** —
which no amount of writing fixes, because the cost was never the reading. It is
knowing a page exists, finding it, and trusting that it describes the version
installed. A tool call removes all three.

Four tools and three prompts were added to the prototype, all driven over the
protocol by `tests/test_mcp_prototype.py` (17 tests).

## The API family — and what it measured

`search_api(query)` finds calls by name or by their first docstring line;
`describe_api(name, include_source=False)` returns the signature, per-argument
types and defaults, the docstring, and `undocumented_parameters`.

That last field exists because the obvious version of this tool does not work.
Measured over the 44 calls in `docs/api-reference.md` against **cellpy 2.1.3**:

```
no docstring at all                                3
one-line docstring                                13
has an Args:/Parameters: section            14 of 44
parameters named in their own docstring   100 of 195   (51%)
```

`CellpyCell.get_cap` takes 23 arguments and documents none of them. A tool that
returned the docstring and stopped would answer half the questions put to it
with a sentence and a shrug — and, worse, would let a model fill the silence.

### Finding 3 — the documentation is usually there, one hop away

`get_cap`'s entire docstring is *"Gets the capacity for the run. See
:func:`cellpy.readers.capacity_curves.get_cap`."* The delegate documents **22 of
its 24 arguments** in a full `Args:` block.

So the text exists. It sits behind a Sphinx cross-reference, which is a marker
only a **docs site** resolves. Everywhere a docstring is actually met — an IDE
tooltip, `help()`, a chat window, an agent — the reader gets the pointer and not
the prose. This is a concrete, mechanical part of why the API docs go unread:
for the thinnest calls, the rendered site is the only place the words appear.

`describe_api` follows the reference. Across the same 44 calls:

```
docstring only          100/195   (51%)
following references    140/195   (72%)
```

Nine calls delegate; five gain arguments. `get_cap` goes from 23 undocumented to
1. That is a 21-point gain from about thirty lines of code, and it costs cellpy
nothing — no docstring has to be rewritten for it to land.

Two things still follow for cellpy itself, and they are cheap:

- **The 28% that remains is a ranked worklist**, not an opinion. `to_csv` (9
  arguments), `CurveOptions` (8), `LoadOptions` (7) and `collect_cycles` /
  `collect_ica` / `collect_dva` (3 each) are the calls where an assistant will
  be guessing.
- **An MCP server changes what a docstring is worth.** Prose on a page nobody
  opens has one reader a month; the same prose in a docstring is read on every
  question anyone asks about that call. It is the strongest argument for writing
  docstrings that cellpy has had.

`include_source=True` is the honest fallback for the rest: a model reads Python
well, and reading `site-packages` is exactly what a chat user cannot do.

### Two smaller traps, both fixed and both tested

- **Re-exports.** `utils.helpers` re-exports `CellpyCell`, so the first index
  answered `get_cap` with `cellpy.utils.helpers.CellpyCell.get_cap` — a true
  path that sends the reader to the wrong file. The index now dedupes by object
  identity and keeps the shortest path, breaking ties toward the defining
  module. (It also shrank the index from 367 entries to 276.)
- **`self` in a rendered signature** invites a model to pass it. Stripped.

### And a boundary

`describe_api("os.system")` must not be a way to import arbitrary modules —
resolving a dotted path *is* importing it, and the caller is a model acting on
text it may have read in a file. Resolution is confined to `cellpy` and
`cellpycore`, and the refusal names that reason rather than falling through to
"no such cellpy call", which is true of `os.system` and teaches the caller that
a different spelling might work.

## Finding 4 — `cellpy new` cannot currently be automated

`list_templates` and `new_project` wrap the batch templating for people who will
not open a terminal. `new_project` works — six notebooks and a `data/` tree,
verified over the protocol — but only because of a workaround.

`create_project(..., no_input=True)` is **not** non-interactive. When the project
directory does not exist, `cli_api.py:1601` calls

```python
cookiecutter.prompt.read_user_yes_no(f"{project_dir} does not exist. Create?", "yes")
```

unconditionally, outside the `no_input` guard. A server has no stdin to answer
with, and under stdio it does not even hang usefully — it raises `ValueError:
I/O operation on closed file`.

`new_project` therefore creates the directory itself before calling in, which
skips the branch entirely. **The upstream fix is one line** — honour `no_input`
at that call — and it is worth making regardless of MCP: it is the difference
between `cellpy new` being scriptable and not.

A second, smaller ask: `cellpy new --list` prints its templates through the UI
and returns nothing, so `list_templates` reads `template_registry` and two
private helpers directly. A `cli_api.list_templates()` returning a dict would
be the honest seam.

## Prompts — the part aimed at people who are not asking for tools

Tools serve someone who already knows what they want. Someone who opens a chat
window and asks it to "do the cell processing" does not, and the gap is not
knowledge of cellpy — it is not knowing that any of this is there.

MCP prompts are the piece of the protocol that addresses exactly this: a client
renders them as named, pickable starting points, so the capability advertises
itself. Three, deliberately few:

- `analyse_cell(path, mass_mg)` — load, check families, render the standard
  plots. When no mass is given it instructs the assistant to *ask* before
  reporting any gravimetric number, because the default of 1.0 mg produces
  numbers that are plausible and wrong.
- `start_batch_project(project, experiment)` — the `cellpy new` walkthrough,
  ending with the one command that opens the notebooks.
- `explain_call(name)` — the API question, with instructions to read source
  rather than guess when `undocumented_parameters` bears on the answer, and to
  say which parts of the answer came from source.

They are also the cheapest place to put the traps that documentation is bad at
preventing, because they are the words the model starts from.

## Starting it locally

There is no deployment budget, and this turns out to matter less than expected:
**stdio needs no server**. The client spawns the process, one per client, which
is also what made the session problem disappear (Finding 1). Nothing has to be
hosted for any of the four groups above to work today.

What it does need is a JSON block in a client config file — a worse ask than the
terminal we were trying to avoid. So the prototype grew `--install`, which
merges a `cellpy` entry into Claude Desktop's config (per-platform path, other
keys preserved, refuses rather than overwrites an unparseable file) and prints
only the block it would add. Verified with `--dry-run`.

### Proposed: `cellpy mcp`, not `cellpy server mcp`

#840 suggests `cellpy server mcp`. Worth reconsidering the spelling: `cellpy
serve` already exists and starts Jupyter, so `cellpy server` would sit one
letter from it — for an audience defined by not being comfortable in a terminal,
that is a real hazard. `cellpy mcp <verb>` collides with nothing:

```
cellpy mcp serve      # run over stdio — what a client spawns
cellpy mcp install    # write the client config block
cellpy mcp status     # registered? which root? which cellpy?
```

**This is compatible with keeping the server out of cellpy.** The subcommand is
a thin shim that imports `cellpy_mcp` and, when it is absent, prints
`pip install cellpy-mcp`. Perhaps forty lines. cellpy gains a *command*, not a
dependency — which is the whole point, given that mcp 2.0 renamed `FastMCP` to
`MCPServer` and ships two `Context` classes with different attributes. The SDK's
churn stays outside cellpy's release cadence, and the discoverable entry point
still lives where people look for it.

One step cannot be removed: somebody types `cellpy mcp install` once. The way to
make that disappear for the chat audience is to fold it into `cellpy setup`,
which they already run — one question, "register cellpy with your chat client?".

### The sandbox default should be cellpy's own paths

`CELLPY_MCP_ROOT` defaults to `~/cellpy_mcp`, which is safe and empty — fine for
a prototype, useless for someone whose cells are already somewhere. But cellpy
was *told* where the data is, during the setup those users have already done:
`config.paths.rawdatadir`, `cellpydatadir`, `outdatadir`, `notebookdir`.

Defaulting the sandbox to that set — a list of roots rather than one — makes the
chat story work with no configuration at all while keeping the boundary meaning
something. It is the difference between "safe and empty" and "safe and useful".

One wrinkle, found while checking: `rawdatadir` can be an **`OtherPath` with a
scheme** (on this machine it is `scp://d1-odin-01…`). The containment check is
`pathlib`-based and cannot express that, so the first version should take the
local roots and say plainly that remote roots are not covered — related to
cellpy-simple-gui#162.

## What is still open

Unchanged from round one, and the first item gets worse now that chat users are
in scope:

- **Long loads block.** `cellpy.get` offers no progress and no cancellation, so
  a client may time out with no signal. A chat user reads that as "it broke".
  This is still the gap most worth closing.
- **No quota, no eviction.** An agent can fill the sandbox; cells live until the
  process exits.
- **Concurrency** is untested, and moot under stdio.
- `new_project` downloads a cookiecutter from GitHub, so CI tests its refusals
  (reached before any network call) and the happy path is verified by hand.

## Recommendation, restated

Unchanged in shape, sharper in the parts #840 asked about:

1. The server lives in a separate **`cellpy-mcp`** package.
2. cellpy grows a thin **`cellpy mcp`** command group and no MCP dependency.
3. Two upstream fixes are worth making on their own merits, MCP or not: honour
   `no_input` in `cellpy new` (one line), and a `cli_api.list_templates()` that
   returns data.
4. The docstring worklist above is the highest-leverage documentation work
   available, because an MCP server is the first reader that actually shows up.

## Proposed upstream — round two

Posted to [cellpy#840](https://github.com/jepegit/cellpy/issues/840#issuecomment-5552632071)
on 2026-09-05: the API-docs measurements, the `cellpy new` finding, the prompts,
and the `cellpy mcp` spelling — again offered rather than prescribed, since the
question of where the server lives is the maintainer's.

Two narrow upstream fixes were filed separately, because both are worth making
whether or not an MCP server ever ships:

- [cellpy#990](https://github.com/jepegit/cellpy/issues/990) — honour `no_input`
  in `cellpy new` (one line at `cli_api.py:1601`); without it `cellpy new`
  cannot be driven from a script, a GUI or a tool.
- [cellpy#991](https://github.com/jepegit/cellpy/issues/991) — a
  `cli_api.list_templates()` that returns data, so a caller need not read
  `template_registry` and two private helpers to offer the same choice.

## Decided (2026-09-05)

Both open questions were settled by the maintainer on cellpy#840:

1. **`cellpy-mcp` is a separate package** that depends on cellpy. It moves at
   the SDK's pace rather than cellpy's release cadence, and the long-lived
   network-facing process — with its security surface — stays out of the
   library. Absorbing it later is easy; extracting it after the fact is not.
2. **The command group is `cellpy mcp <verb>`**, not `cellpy server mcp`.
   `cellpy serve` already starts Jupyter, and one letter is too close for an
   audience defined by not being comfortable in a terminal.

The two are compatible because the subcommand carries no MCP dependency: it
imports `cellpy_mcp` and, when that is absent, says how to install it. **cellpy
gains a command, not a dependency.**

What follows from the decision, in the order it should be built:

- `cellpy mcp serve | install | status` in cellpy, as a thin shim (~40 lines).
  `serve` execs the installed server over stdio; `install` writes the client
  config block; `status` reports whether it is registered, against which root
  and which cellpy.
- The `cellpy-mcp` package itself, seeded from
  [`examples/mcp/server.py`](../../examples/mcp/server.py) — which is a
  prototype, so the seeding is a rewrite with tests, not a copy.
- The sandbox default moves from `~/cellpy_mcp` to cellpy's own configured
  paths (`config.paths.rawdatadir`, `cellpydatadir`, `outdatadir`,
  `notebookdir`) as a list of roots — local ones only, since `rawdatadir` can
  carry a scheme (`scp://…`).
- Folding `cellpy mcp install` into `cellpy setup` as one question, so the
  chat audience never types a command at all.

The prototype in this repo stays where it is: it is the thing the decision was
made from, and it will keep answering questions that the package should not
have to be rebuilt to test.
