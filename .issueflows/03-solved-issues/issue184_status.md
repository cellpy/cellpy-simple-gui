# Status — #184 update plots when the Manage cells modal closes

- [x] Done

Branch: `cursor/184-defer-replot-cells-modal-713a` (stacked on
`cursor/186-y-ranges-group-avg-spread-713a`, PR #189, because merging from
this environment is not possible — read-only GitHub token).

## What's done

- `app.js`: `_replotAfterEdit()` defers the redraw while `cellsManagerOpen`
  (flag `_replotOnClose`); `closeCellsManager()` redraws once. `updateCell`,
  `selectAll`, `selectGroup`, `removeCell` use it; sidebar edits unchanged.
- `app.js`: per-chart request sequence (`_plotSeq`) via `_fetchFigure` — a
  response overtaken by a newer request is dropped, never drawn
  (`summary` / `cycles` / `cell` incl. compare). `plotBusy` backed by an
  in-flight counter so the spinner stays up until the last request settles.
- Modal footer hint ("Plots refresh when this dialog closes." → "Edits saved —
  …" once something changed); `.mgr-foot-hint` style.
- e2e (`tests/test_gui_playwright.py::test_cells_modal_defers_plot_refresh_until_close`):
  label + group + none/all edits in the modal issue **0** `/api/plots/*`
  requests; Close issues exactly **1**; reopen/close without edits issues none.
  Fails on the previous JS, passes now. Whole e2e module green locally
  (Playwright + Chromium installed for this session; CI still runs
  `-m essential` only).
- Manual walkthrough in `--server` mode recorded:
  `/opt/cursor/artifacts/cells_modal_deferred_replot_184.mp4`.
- Design note added to `04-designs-and-guides/manage-cells-modal.md`.

## Remaining work

- None.
