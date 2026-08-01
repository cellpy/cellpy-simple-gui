# Issue #62 status

- [x] Done

## What's done

- Plan accepted (Mute by group; disable when N/A; Cycles sidepane).
- `group_legend_muting` on `SummaryPlotSpec` / `CyclesPlotSpec`; forwarded in `plotting.summary_figure` / `cycles_figure`.
- UI checkboxes on Cycle summary (disabled when Group avg) and Cycles sidepane (disabled when per_cell).
- Tests: `test_summary_figure_forwards_group_legend_muting`, `test_cycles_figure_forwards_group_legend_muting`.
- Design note: `.issueflows/04-designs-and-guides/group-legend-muting.md`.
- `uv run --extra dev pytest` green.

## Remaining work

- None (ship via PR).
