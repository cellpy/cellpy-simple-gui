# Status — Issue #3: Manage cells expanded editor

- [x] Done

## What's done

- Plan accepted: centered modal + dense table.
- Sidebar **Manage** button opens modal; Esc / backdrop / Close dismiss.
- Table edits reuse `updateCell` / `selectAll` / `clearAll` / `removeCell` (selected, label, group, mass, remove).
- Filter by name, sort (library order / group / name), select-by-group (client-side).
- Modal CSS themed with existing tokens; design note in `04-designs-and-guides/manage-cells-modal.md`.
- API test asserts mass round-trip; `uv run pytest` green (44 passed).

## Remaining work

- None for this issue.
