# Issue #86 — Plan: edit nominal-capacity basis

## Goal

Let each Manage Cells row show and edit `nom_cap_specifics` (gravimetric / areal / absolute), defaulting from the loaded cellpy meta, remaking the summary on change, and showing the matching nom. cap unit (mAh/g / mAh/cm² / mAh).

## Constraints

- cellpy boundary: only `core/cellpy_adapter.py` talks to cellpy.
- Extend the #69 physical-meta path (`apply_physical_meta` / `JournalRowUpdate` / Manage Cells) — no second UI.
- Default from file/meta per cell; never force a global “gravimetric” default over cellpy’s value.
- Full `make_summary()` on change (no selective rebuild; see CELLPY_PAINPOINTS §21).
- Out of scope: Cell explorer editing; inventing basis conversion beyond cellpy’s assign + remake.

### Prior art

- #69 Manage Cells physical meta: mass / area / nominal_capacity / cycle_mode via `apply_physical_meta` ([`cellpy_adapter.py`](../../../src/cellpy_simple_gui/core/cellpy_adapter.py), [`library.py`](../../../src/cellpy_simple_gui/core/library.py)).
- Ingest already passes `nom_cap_specifics` into `cellpy.get` ([`IngestRequest`](../../../src/cellpy_simple_gui/core/models.py), ingest form select).
- `CapacityMode` literal = `gravimetric | areal | absolute`; `CAPACITY_UNITS` maps to display units.
- CellpyCell exposes `nom_cap_specifics` (readable/settable; probed for #86); persists in `.cellpy`.
- Manage Cells design: [manage-cells-modal.md](../../04-designs-and-guides/manage-cells-modal.md).
- Toolbox: none. Graph: cells / adapter / Manage Cells communities.

## Approach

1. **`read_meta`** — Include `nom_cap_specifics` when it is a valid `CapacityMode`; else `None`.
2. **Adapter** — Extend `apply_physical_meta(..., nom_cap_specifics=...)` to assign `cell.nom_cap_specifics` and remake summary once with other fields. Thin `set_nom_cap_specifics` wrapper optional.
3. **Models / library** — Add `nom_cap_specifics` to `CellMeta`, `JournalRowUpdate`, `CellRecord`, `to_meta` / `_apply_physical_meta` / `add_cell` / `restore_cell` / `Library.update`.
4. **API** — Pass through in `cells.update_cell`.
5. **UI** — Manage Cells: add a **Basis** select (Gravimetric / Areal / Absolute) beside nom. cap. Replace hard-coded `Nom. cap (mAh/g)` header with `Nom. cap` plus a per-row unit hint (e.g. small suffix or `title` / adjacent text from `CAPACITY_UNITS[c.nom_cap_specifics]`). Prefer per-row unit so mixed-basis libraries stay correct.
6. **Client** — `updateCell` treats empty basis like cycle_mode (omit); replot after change.
7. **Docs** — Update `manage-cells-modal.md`. Painpoint only if setter/read is flaky or units disagree with basis.
8. **Tests** — Extend API edit + project round-trip (+ core read_meta / apply) for `nom_cap_specifics`.

## Files to touch

| Path | Change |
|------|--------|
| `src/cellpy_simple_gui/core/cellpy_adapter.py` | `read_meta` + `apply_physical_meta` |
| `src/cellpy_simple_gui/core/library.py` | record / update wiring |
| `src/cellpy_simple_gui/core/models.py` | `CellMeta` + `JournalRowUpdate` |
| `src/cellpy_simple_gui/api/routers/cells.py` | pass field |
| `src/cellpy_simple_gui/web/templates/index.html` | Basis column + dynamic unit |
| `src/cellpy_simple_gui/web/static/js/app.js` | empty-value handling; optional unit helper |
| `src/cellpy_simple_gui/web/static/css/app.css` | column width if needed |
| `tests/test_api.py`, `test_core.py`, `test_projects.py` | cover basis |
| `.issueflows/04-designs-and-guides/manage-cells-modal.md` | document field |

## Test strategy

- `uv run pytest`
- Assert API update sets `nom_cap_specifics` and returns it on `CellMeta`.
- Assert `read_meta` / apply / project save-open preserve basis.
- No Playwright required.

## Open questions

1. **Header vs per-row unit** — Recommended: column header **Nom. cap** + per-row unit text (from basis). Agree?
2. **Empty / unknown basis** — Recommended: select shows placeholder “—” and unit falls back to `mAh/g` only for display when meta missing; do not write a default into the cell until the user picks. Agree?
