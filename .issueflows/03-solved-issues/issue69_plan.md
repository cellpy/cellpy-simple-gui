# Issue #69 — Plan: edit cell metadata

## Goal

Let users edit physical cell metadata (mass already works; add area, nominal capacity, and cycle mode) from Manage Cells, persist through the existing update/save path, and refresh summaries so plots/C-rates/gravimetric values stay consistent. Document cellpy gaps around selective summary recalculation in `CELLPY_PAINPOINTS.md`.

## Constraints

- cellpy boundary: only `core/cellpy_adapter.py` (and existing `collect`) talk to cellpy.
- Reuse Manage Cells + `POST /api/cells/{id}/update` / `updateCell` — do not add a second mass/meta UI.
- Org fields (`label`, `group`, `selected`) stay separate from physical meta.
- Prefer full `make_summary()` for v1 (same as today’s `set_mass`); do **not** invent a meta→summary dependency graph in this app.
- Out of scope for this PR: editable Cell explorer metrics; job-wrapping slow rebuilds; upstream cellpy dependency-graph implementation (report only).

### Prior art

- Manage Cells modal design: [`.issueflows/04-designs-and-guides/manage-cells-modal.md`](../../04-designs-and-guides/manage-cells-modal.md) — mass already editable via `updateCell`.
- `adapter.set_mass` → assign + `cell.make_summary()` ([`cellpy_adapter.py`](../../../src/cellpy_simple_gui/core/cellpy_adapter.py)).
- `Library.update` applies mass only among physical fields; refreshes mass/area/nominal from `read_meta` ([`library.py`](../../../src/cellpy_simple_gui/core/library.py)).
- `JournalRowUpdate` wire model already has `mass` ([`models.py`](../../../src/cellpy_simple_gui/core/models.py)).
- Ingest form already collects mass/area/nominal at load time; post-load edit is the gap.
- Tests: `test_edit_cell` (API mass), project round-trip with mass — extend these.
- Toolbox: none relevant.
- Graph: cells / Manage Cells / adapter communities align with above; no conflicting prior plan for selective recalc.

## Approach

1. **Adapter** — Add `set_area` / `set_nominal_capacity` / `set_cycle_mode` (or a small `update_physical_meta` that dispatches), mirroring `set_mass`: set cellpy attributes (`active_electrode_area`, `nominal_capacity`, `cycle_mode`) and call `make_summary()` with the same warning-swallow pattern. Probe cellpy for existing setters / how cycle_mode is stored; if attribute assignment or a fuller reprocess is required, note it as a painpoint.
2. **Library + API models** — Extend `CellMeta`, `JournalRowUpdate`, and `Library.update` with optional `area` / `nominal_capacity` / `cycle_mode` (`CycleMode` literal, same as ingest). Positive / sensible validation for numerics consistent with mass. After any physical change, refresh record meta from `read_meta` (include `cycle_mode` in `read_meta`).
3. **UI** — Manage Cells table: add editable Area, Nom. cap, and Cycle mode (select: anode / cathode / full_cell) beside Mass; wire `@change` → `updateCell`. Keep Cell explorer metrics read-only for this issue. Sidebar mass display stays as-is.
4. **Client** — Reuse `updateCell` + `replotCurrent()`; extend null/empty handling for new numeric fields like mass; cycle_mode as string select.
5. **Painpoints** — After implementation spikes, append `CELLPY_PAINPOINTS.md`: whether `make_summary` is all-or-nothing, missing setters, cycle_mode post-load edit quirks, and the wish for a param→summary-column dependency graph (from issue comments).
6. **Design note** — Short update to `manage-cells-modal.md` listing the new editable columns.
7. **Persist** — Ensure project save/open round-trips cycle_mode (via `.cellpy` after setter, and/or manifest if needed).

## Files to touch

| Path | Change |
|------|--------|
| `src/cellpy_simple_gui/core/cellpy_adapter.py` | `set_area` / `set_nominal_capacity` / `set_cycle_mode` (+ `read_meta`) + `make_summary` |
| `src/cellpy_simple_gui/core/library.py` | `update(...)` / `CellRecord` accept area / nominal_capacity / cycle_mode |
| `src/cellpy_simple_gui/core/models.py` | `CellMeta` + `JournalRowUpdate` fields |
| `src/cellpy_simple_gui/core/projects.py` | Manifest/record fields if cycle_mode must round-trip outside `.cellpy` |
| `src/cellpy_simple_gui/api/routers/cells.py` | Pass new fields through |
| `src/cellpy_simple_gui/web/templates/index.html` | Manage Cells columns + cycle_mode select |
| `src/cellpy_simple_gui/web/static/js/app.js` | `updateCell` empty-value handling if needed |
| `src/cellpy_simple_gui/web/static/css/app.css` | Only if column layout needs a tweak |
| `tests/test_api.py` (+ optional `test_core.py` / projects) | Edit area/nom. cap/cycle_mode; assert meta/summary path |
| `CELLPY_PAINPOINTS.md` | Selective-recalc / meta dependency notes |
| `.issueflows/04-designs-and-guides/manage-cells-modal.md` | Document new fields |

## Test strategy

- `uv run pytest` (full suite).
- Extend `test_edit_cell` for area + nominal_capacity + cycle_mode API updates.
- Prefer a small core/API assert that after nom. cap or mass change, a summary column moves (or at least `make_summary` path doesn’t error and meta round-trips) — no Playwright/pixel asserts required for this issue.
- Project save/open round-trip for the new fields if cheap to add beside existing mass test.

## Open questions

1. **v1 fields** — **Resolved:** mass (keep) + area + nominal_capacity + **cycle_mode**. Still out: `nom_cap_specifics`.
2. **UI surface** — Recommended: **Manage Cells only** this PR (explorer stays read-only). Agree?
3. **Recalc** — Recommended: **always full `make_summary()`** (parity with mass); selective rebuild is a painpoint report, not app logic. Agree?
4. **Scope split** — This plan is one PR-sized MVP. If you want explorer editing or a job-backed rebuild UX, park those as follow-ups rather than growing this issue.
