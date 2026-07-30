# Group average + static figure export

From issue #27 (`/iflow-fix`).

## Group average with mixed group sizes

**Context:** cellpy `group_it=True` silently disables averaging when *any*
selected group has &lt; 2 cells (all-or-nothing). See `CELLPY_PAINPOINTS.md` §3.

**Decision:** When the UI asks for group average, partition selected cells into
multi-member vs singleton groups (`collect.partition_by_group_size` /
`summary_collections`). Average only the multi set; keep singletons as plain
per-cell series (no spread); merge Plotly traces / unify export frames.

**Alternatives:** Drop singletons from the plot; wait for an upstream collect
fix. Rejected for UX — checkbox looked broken on real projects.

## Static figure export (PNG / SVG / PDF)

**Context:** `Collection.save` is data-only; `plotutils.save_image_files` is
disk + subprocess. Apps need in-memory bytes (`CELLPY_PAINPOINTS.md` §13).

**Decision:** Build the same figure as the UI (`plotting.summary_figure` /
`cycles_figure`), then `fig.write_image` (kaleido) for download. Export menu
splits Data vs Figure; missing kaleido → clear 503 + `uv sync --extra export`.
