# Issue #27 status — Iterative fixes: group average checkbox

Interactive `/iflow-fix` session.

- [x] Done

## Iterative fixes log

- 2026-07-30 — **Group avg + singletons:** cellpy’s `group_it` silently skips
  averaging when any selected group has &lt; 2 cells. App now partitions
  multi-member vs singleton groups, averages only the multi set (spread ok),
  plots/exports singletons as plain series, and merges figures. Updated
  `CELLPY_PAINPOINTS.md` §3. Regression: `test_group_average_keeps_singleton_traces`.

- 2026-07-30 — **Painpoint §13:** documented missing app-friendly static figure
  export on the collect path (`Collection.save` is data-only;
  `plotutils.save_image_files` is disk/subprocess). Wish: in-memory
  `to_image` / `write_image` bytes API.

- 2026-07-30 — **Figure Export ▾ (PNG/SVG/PDF):** Export menus split into Data +
  Figure; same `/api/export/summary|cycles` endpoints accept image fmts and
  render via Plotly/`write_image` (kaleido). Clear 503 toast if extra missing.
  README updated. Test: `test_summary_figure_export_svg` (skipped without kaleido).
