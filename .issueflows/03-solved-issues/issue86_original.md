# Issue #86: Manage Cells: edit nominal-capacity basis (gravimetric / areal / absolute)

Source: https://github.com/cellpy/cellpy-simple-gui/issues/86

## Original issue text

## Problem / context

After #69, Manage Cells can edit nominal capacity, but not the **basis** (`nom_cap_specifics`: gravimetric / areal / absolute). That basis lives on the cellpy cell (and in the `.cellpy` file) and changes how the nominal-capacity value is interpreted (units: mAh/g vs mAh/cm² vs mAh). Ingest already exposes the knob; post-load edit does not.

## Spec

- Expose per-cell `nom_cap_specifics` in Manage Cells (select: Gravimetric / Areal / Absolute), next to the nom. cap value.
- Default each row from cellpy metadata (`cell.nom_cap_specifics` via `read_meta` / `CellMeta`) — do not invent a global default that overrides the file.
- Wire through `JournalRowUpdate` → `Library.update` → adapter (assign + full `make_summary()`, same as other physical meta in #69).
- Persist via project `.cellpy` save/open (round-trip).
- Update the nom. cap column unit label (or per-row hint) so it matches the selected basis (mAh/g / mAh/cm² / mAh), not a hard-coded gravimetric label.
- If reading/setting the basis is awkward in cellpy, note it in `CELLPY_PAINPOINTS.md`.

## Acceptance criteria

- [ ] Manage Cells shows a per-cell basis control; initial value matches the loaded cellpy meta.
- [ ] Changing basis updates the in-memory cell, remakes summary, and survives project save/open.
- [ ] Nom. cap unit display reflects the current basis.
- [ ] API/core test covers update + round-trip (or meta read) for `nom_cap_specifics`.
- [ ] Per-cell (non–group) hover/plots still work; no regression on mass/area/nom.cap/cycle_mode edits.

## Out of scope

- Editable Cell explorer metrics.
- Selective summary rebuild (still full `make_summary()`; see CELLPY_PAINPOINTS §21).
- Changing how cellpy converts between bases (value reinterpretation beyond what cellpy does on assign + remake).
