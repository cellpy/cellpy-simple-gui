# Issue #32: Plot appearance options: color scheme and figure theme

Source: https://github.com/cellpy/cellpy-simple-gui/issues/32

## Original issue text

## Problem / context

Summary and cell plots always get the same hard-coded look: `collect._restyle` forces a white card + Inter-ish fonts, and series colors come from a fixed `library.PALETTE` / cellpy defaults. The app shell has light/dark UI themes, but figures do not follow them, and users cannot pick a color scheme or figure theme for screen or export. cellpy exposes `cellpy.plotting.theme` / `make_plotly_template` (and painpoint §11 asks for a theme hook); we should lean on that where it helps instead of only growing our restyle glue.

## Spec

- Add user-facing controls for **figure theme** (e.g. light / dark / match app shell) and **color scheme** (a small curated set — cellpy/default + 1–2 readable palettes).
- Apply choices to **summary** and **cell explorer** plots (and to static figure export, which reuses the same figure builders).
- Persist selection for the session (localStorage is fine for v1).
- Prefer cellpy plotting theme/template APIs when they cover the need; keep a thin app restyle only for legend/facet polish we already own.
- Document any new cellpy friction in `CELLPY_PAINPOINTS.md`.

## Acceptance criteria

- [ ] UI control(s) to choose figure theme and color scheme without leaving the plot tabs.
- [ ] Changing either option re-renders the current plot with the new look.
- [ ] Dark figure theme is readable in the dark app shell; light theme remains suitable for export.
- [ ] Exported PNG/SVG/PDF use the same theme/scheme as the on-screen figure.
- [ ] Tests cover at least one theme/scheme path through the figure builder (no brittle pixel asserts).

## Out of scope

- Full custom color pickers per cell/group.
- Matplotlib backend / non-Plotly export.
- Changing the app chrome theme system itself (only how plots relate to it).

## Comments (curated summary)

- **Additional tasks**:
  - Bump the app's cellpy dependency to **v2.1.1.post2** (includes per-panel y-limits / clearer `share_y` for collected summary facet plots — cellpy#804).

_Note: this section is an interpretive summary of the comment thread, not a verbatim dump. Source comments: 1, last comment by @jepegit on 2026-07-30._
