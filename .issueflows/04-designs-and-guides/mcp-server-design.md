# An MCP server for cellpy — design, and what a prototype found

Written 2026-08-17 for [#128](https://github.com/cellpy/cellpy-simple-gui/issues/128),
against **cellpy 2.1.2** and the **mcp 2.0.0** Python SDK. Scoped deliberately:
design and prototype, not ship.

The prototype is [`examples/mcp/server.py`](../../examples/mcp/server.py) —
eight tools, driven end to end over the real MCP protocol. Everything below that
sounds like an opinion was measured.

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

## Reproducing

```bash
CELLPY_MCP_ROOT=/some/data uv run --script examples/mcp/server.py
```

`tests/test_mcp_prototype.py` drives it over the protocol with an in-process
client. It skips when `mcp` is not installed — install with
`uv sync --extra mcp`.
