# Issue #188 — bulk edits in the Manage cells modal

## Goal

Let the Manage cells modal apply one change to every checked cell in the current name filter: set group, basis, or cycle mode, or set / scale the float fields (mass, area, nominal capacity). Per-cell editors stay as they are.

## Constraints

- Single-cell `POST /api/cells/{id}/update` and `Library.update` stay the write path. A bulk call is a loop over that path, not a second persistence model.
- Physical numbers still have to be `> 0`. `apply_physical_meta` already drops non-positive mass, area, and nominal capacity; bulk must not invent a way to store them.
- Modal edits still do not redraw until the dialog closes (`_replotAfterEdit`, issue #184). One bulk apply flags that once.
- Labels stay per cell. Bulk does not set label, selection, or cycles, and it does not add a second remove-selected control (`remove all` and the row × already exist).
- The maintainer comment about loading cells through this modal is **out of this plan**. Loading already has the Add cells modal ([loading-ui.md](../04-designs-and-guides/loading-ui.md)).

### Prior art

- `Library.update` and `JournalRowUpdate` in [library.py](../../src/cellpy_simple_gui/core/library.py) / [models.py](../../src/cellpy_simple_gui/core/models.py) — coexist. Bulk computes each new float, then calls `update`.
- `apply_physical_meta` in [cellpy_adapter.py](../../src/cellpy_simple_gui/core/cellpy_adapter.py) — reuse. It assigns meta and refreshes the summary. Do not reimplement that.
- `selectGroup()` in [app.js](../../src/cellpy_simple_gui/web/static/js/app.js) — same idea (many cells, one intention) but one HTTP call per cell. Do not copy that loop for this; one bulk request, one `_applyState`.
- Checkboxes, `filteredSortedCells`, and `POST /api/cells/select` — the target set is chosen with those. Export already means "selected cells"; bulk uses the same `selected` flag, narrowed by the name filter the user is looking at.
- [manage-cells-modal.md](../04-designs-and-guides/manage-cells-modal.md) — extend with a short decision section. Do not move the modal or change single-row editors.
- Toolbox (`.issueflows/00-tools/README.md`): no helper. `graphify-out/GRAPH_REPORT.md` is absent.

## Approach

**Who it applies to.** Checked cells that are visible under the current name filter (`filteredSortedCells` where `selected`). A checked cell hidden by the filter is left alone. An empty filter means every checked cell.

**What one apply can do.** Exactly one field per click:

- Floats `mass`, `area`, `nominal_capacity`: `set`, `mul`, `div`, `add`, or `sub` against that cell's current value. `set` replaces it. Example: mass × 1000.
- `group` (integer ≥ 1), `nom_cap_specifics` (`gravimetric` / `areal` / `absolute`), `cycle_mode` (`anode` / `cathode` / `full_cell`): set only.

**Server.** `POST /api/cells/bulk` with a new `BulkCellUpdate` model: `cell_ids` (non-empty) plus exactly one of those fields. Float fields are `{op, value}`.

Before any write:

- Unknown id → 404, nothing written.
- No field, or more than one field → 400.
- `div` by 0, non-finite `value`, or `group < 1` → 400, nothing written.
- For `mul` / `div` / `add` / `sub`, a cell with no current number for that field is skipped.
- A result that is not finite or not `> 0` is skipped for that cell (same rule as `apply_physical_meta`).

Then each remaining id goes through `Library.update`. Response is the usual library `state` plus `updated` (count) and `skipped` (`[{id, field, reason}]`). Summary refresh stays inside `apply_physical_meta`, once per cell that actually changed.

**UI.** A second row on the Manage cells toolbar (`.mgr-bulk`): field, and for floats an operator (`=`, `×`, `÷`, `+`, `−`) plus a number; for group a number; for basis and cycle mode the same choices as the row editors. Button label `Apply to N`, disabled when N is 0 or the value is empty. N is the target count above. One `applyBulk()` posts the ids, replaces state, `markDirty()`, `_replotAfterEdit()`. If `skipped` is non-empty, a short notice names how many were left unchanged. Per-row inputs are untouched.

## Files to touch

- [src/cellpy_simple_gui/core/models.py](../../src/cellpy_simple_gui/core/models.py) — `NumericEdit` and `BulkCellUpdate`.
- [src/cellpy_simple_gui/core/library.py](../../src/cellpy_simple_gui/core/library.py) — `bulk_update` that validates, computes, and calls `update` per id.
- [src/cellpy_simple_gui/api/routers/cells.py](../../src/cellpy_simple_gui/api/routers/cells.py) — `POST /api/cells/bulk`.
- [src/cellpy_simple_gui/web/static/js/app.js](../../src/cellpy_simple_gui/web/static/js/app.js) — `applyBulk()`.
- [src/cellpy_simple_gui/web/templates/index.html](../../src/cellpy_simple_gui/web/templates/index.html) — bulk toolbar row.
- [src/cellpy_simple_gui/web/static/css/app.css](../../src/cellpy_simple_gui/web/static/css/app.css) — only if the second row needs a layout rule.
- [tests/test_api.py](../../tests/test_api.py) — bulk cases (below).
- [.issueflows/04-designs-and-guides/manage-cells-modal.md](../04-designs-and-guides/manage-cells-modal.md) — short #188 decision.

## Test strategy

`uv run pytest` from the worktree (the documented suite). New API tests, using the existing loaded-cell client fixture:

- × on mass for two cells updates both and returns one state.
- set group on two cells.
- unknown id → 404 and the other cell unchanged.
- ÷ 0 → 400 and nothing written.
- a non-positive result is skipped and reported; a valid set of another field in a separate request still works.
- empty `cell_ids` → 422.

No new Playwright coverage. The change is a toolbar control on an existing modal; the API tests lock the arithmetic and the skip rules.

## Open questions

- **Loading cells from this modal** (comment on #188: add cells, and create a project from scratch). This plan leaves that out. Accept = defer it. Revise if it belongs in this PR — that would be a second deliverable, and `/iflow-issue split` would fit better than growing this one.
- Target set is **checked ∩ current name filter**. Revise if bulk should ignore the filter and hit every checked cell, including ones the filter is hiding.
