# Issue #37: Spread bands too opaque for safe/muted color schemes

Source: https://github.com/cellpy/cellpy-simple-gui/issues/37

## Original issue text

## Problem / context

With group-average **Spread** on, the mean ± std bands look correctly translucent under the **cellpy** color scheme, but under **safe** / **muted** (#32) they render as nearly solid blocks that hide gridlines and overlapping series. Screenshot: Match app + muted + Spread — bands are dense opaque fills.

Likely cause: `collect._apply_colorway` assigns a solid hex `fillcolor` to filled traces. Plotly spread fills need an **alpha** in the fill color (rgba / transparent hex); setting `tr.opacity` alone is easy to get wrong (either ignored for fill, or also washing out the mean line).

## Spec

- When applying a non-`cellpy` colorway to spread/fill traces, use a translucent fill (e.g. rgba with ~0.2–0.35 alpha) while keeping the mean **line** fully opaque.
- Preserve series color identity (safe/muted palettes); only fix transparency.
- Leave `cellpy` default path unchanged (no forced colorway).
- Cover with a small structural test (fillcolor has alpha / rgba), not pixel asserts.

## Acceptance criteria

- [ ] Summary plot with Group avg + Spread + **safe** (and **muted**): bands are clearly see-through; grid and overlapping bands remain readable.
- [ ] Mean lines stay solid/opaque at full series color.
- [ ] `cellpy` color scheme spread appearance stays at least as good as today.
- [ ] Test asserts translucent fill for a safe/muted restyle path.

## Out of scope

- New color schemes or per-series opacity controls in the UI.
- Chart-card / pane theming (#36).
- Changing cellpy’s upstream spread styling.
