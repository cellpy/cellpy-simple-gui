# Issue #3: Make the Cells list workable for many cells (modal or expanded editor)

Source: https://github.com/cellpy/cellpy-simple-gui/issues/3

## Original issue text

## Problem / context

The sidebar **Cells** pane is hard to use once many cells are loaded. Cards are tall and the column is narrow (~330px), so selecting, renaming, and especially editing **grp** means a lot of scrolling and fiddly targets. Bulk actions today are only `all` / `none` / `clear`.

The compact sidebar list is still useful as a quick overview; the gap is a roomier place to manage the library.

## Spec

Add a primary way to manage many cells without fighting the sidebar. Preferred direction (confirm in plan):

1. Keep the sidebar list as a compact overview (selection + identity).
2. Add an **Expand / Manage cells** action that opens a **modal or large drawer** with a denser table (or spreadsheet-like grid) for the same library fields the sidebar already edits: selected, label/name, group, remove — and room for mass/cycles display (and mass edit if the API already supports it).
3. Preserve existing update semantics (`updateCell` / journal-style patches); no new persistence model.
4. Optional niceties if cheap: filter/search by name, sort by group/name, select-by-group.

Decide in `/iflow-plan` between modal vs full-width drawer vs resizable sidebar; do not ship both.

## Acceptance criteria

- [ ] With ≥20 cells loaded, a user can select, rename, change group, and remove cells without relying only on the cramped sidebar cards.
- [ ] Sidebar still shows the current library and stays in sync after edits in the expanded UI.
- [ ] `all` / `none` / `clear` (or equivalents) remain available in the expanded UI.
- [ ] Keyboard/focus usable in the expanded UI (tab through fields; Esc closes modal/drawer).
- [ ] Dark/light themes look intentional; layout works in the desktop shell and `--server` browser.

## Out of scope

- Full journal file round-trip / Excel import-export.
- Plot legend long-name fix (#1) and y-axis limits (#2).
- Virtualized rendering unless needed for real lag at typical journal sizes.
