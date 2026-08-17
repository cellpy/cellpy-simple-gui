# cellpy MCP server (prototype)

Eight tools that let an agent load battery cells, collect them, and render or
export the result — without writing any Python.

**This is a prototype.** It exists to answer the two questions in
[#128](https://github.com/cellpy/cellpy-simple-gui/issues/128) by building the
thing rather than reasoning about it. The findings, and the recommendation, are
in [`mcp-server-design.md`](../../.issueflows/04-designs-and-guides/mcp-server-design.md).

## Run it

```bash
CELLPY_MCP_ROOT=/path/to/your/cell/files uv run --script examples/mcp/server.py
```

It speaks stdio, so point an MCP client at that command. In Claude Code:

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

## Three things it does on purpose

**Handles, not data.** Only `preview_collection` returns rows. A tool result
goes into a model's context window, and one collected summary is ~29 kB of CSV
while a raw figure can be 7 MB.

**Results carry the traps.** `render` returns `trace_types` alongside
`points_plotted` and `rows_collected`, so an agent that asked for a density film
can see it got `histogram2d` rather than lines, and one that forgot
`direction="both"` can see it plotted 891 of 2328 rows. Those are the failures
that otherwise look plausible.

**One client per process.** State is process-wide, deliberately: mcp 2.0 does
not give a tool a stable session identity, and under stdio each client spawns its
own process anyway. Do not put this behind a shared HTTP endpoint as written.

## Limits worth knowing before you rely on it

- No quota — an agent can fill the sandbox with figures.
- `load_cell` blocks, with no progress and no cancellation.
- Cells stay in memory until the process ends.
- Built against mcp 2.0.0, which is young and moving.
