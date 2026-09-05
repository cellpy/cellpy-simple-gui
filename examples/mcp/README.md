# cellpy MCP server (prototype)

Twelve tools and three prompts that let an agent — or a chat window — load
battery cells, collect them, render or export the result, look up how any cellpy
call works, and set up a batch project. Without writing any Python.

**This is a prototype.** It exists to answer questions by building the thing
rather than reasoning about it: first the two in
[#128](https://github.com/cellpy/cellpy-simple-gui/issues/128), then the four
audiences raised in [cellpy#840](https://github.com/jepegit/cellpy/issues/840).
The findings and the recommendation are in
[`mcp-server-design.md`](../../.issueflows/04-designs-and-guides/mcp-server-design.md).

## Run it

```bash
CELLPY_MCP_ROOT=/path/to/your/cell/files uv run --script examples/mcp/server.py
```

It speaks stdio, so point an MCP client at that command. Or let it write the
config itself:

```bash
CELLPY_MCP_ROOT=/path/to/your/cell/files uv run --script examples/mcp/server.py --install
```

That merges a `cellpy` entry into Claude Desktop's config, leaving your other
servers alone. Add `--dry-run` to see the block first. To do it by hand:

```json
{
  "mcpServers": {
    "cellpy": {
      "command": "uv",
      "args": ["run", "--script", "/abs/path/to/examples/mcp/server.py"],
      "env": { "CELLPY_MCP_ROOT": "/path/to/your/cell/files" }
    }
  }
}
```

`CELLPY_MCP_ROOT` is the **only** directory the server will read or write.
It defaults to `~/cellpy_mcp` rather than to your filesystem.

## The tools

Cells and figures:

| Tool | What it gives you |
|---|---|
| `list_instruments` | loaders, and whether each can actually run on this machine |
| `load_cell` | a handle, cycle count, mass, summary column names |
| `list_cells` | what is loaded |
| `describe_plot_families` | the 20 summary families, marked available or missing-columns |
| `collect` | a handle, row count, columns, `is_grouped`, direction counts |
| `preview_collection` | a few rows, capped at 20 |
| `render` | writes a figure; returns trace types and points plotted |
| `export_collection` | writes csv/parquet/json; returns rows and bytes |

The API surface — "how does this call work, and what are its arguments":

| Tool | What it gives you |
|---|---|
| `search_api` | calls matching a name or a docstring line, from the installed cellpy |
| `describe_api` | signature, per-argument types and defaults, docstring, `undocumented_parameters`, optionally source |

Batch templating — `cellpy new` for people who will not open a terminal:

| Tool | What it gives you |
|---|---|
| `list_templates` | registered and local templates, and which is the default |
| `new_project` | a project from a template; returns the notebooks it made |

## The prompts

For the user who opens a chat window and does not know that any of this exists:
`analyse_cell`, `start_batch_project`, `explain_call`. A client shows them as
pickable starting points, so the capability advertises itself.

## Four things it does on purpose

**Handles, not data.** Only `preview_collection` returns rows. A tool result
goes into a model's context window, and one collected summary is ~29 kB of CSV
while a raw figure can be 7 MB.

**Results carry the traps.** `render` returns `trace_types` alongside
`points_plotted` and `rows_collected`, so an agent that asked for a density film
can see it got `histogram2d` rather than lines, and one that forgot
`direction="both"` can see it plotted 891 of 2328 rows. `describe_api` returns
`undocumented_parameters` for the same reason: cellpy documents about half its
arguments, and a model should know when the package never said.

**It follows the docstring's own cross-references.** `CellpyCell.get_cap` takes
23 arguments, documents none, and points at
`cellpy.readers.capacity_curves.get_cap` — which documents 22 of 24. Following
that reference takes argument coverage across the documented API from 51% to
72%. Only a docs site resolves those markers; nobody reading a docstring does.

**One client per process.** State is process-wide, deliberately: mcp 2.0 does
not give a tool a stable session identity, and under stdio each client spawns
its own process anyway. Do not put this behind a shared HTTP endpoint as written.

## Limits worth knowing before you rely on it

- No quota — an agent can fill the sandbox with figures.
- `load_cell` blocks, with no progress and no cancellation.
- Cells stay in memory until the process ends.
- `new_project` has to create the project directory itself, because
  `cellpy new` prompts even with `no_input=True` (`cli_api.py:1601`). It also
  downloads a cookiecutter from GitHub on first use.
- Built against mcp 2.0.0, which is young and moving.
