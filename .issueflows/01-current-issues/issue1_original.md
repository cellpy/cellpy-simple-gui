# Issue #1: Fix Plotly summary legend when cell names are very long

Source: https://github.com/cellpy/cellpy-simple-gui/issues/1

## Original issue text

## Problem / context

On the Summary Plot, long cell (or group) names blow up the Plotly legend and wreck the layout: legend text overlaps facet strip labels and y-axes, and the data area is horizontally squashed.

Reproduced with many selected cells / group-average style labels (e.g. concatenated ids like `20130419_es018_02_eth_01-20130419_es018_02_eth_03-…`) on a faceted summary figure (Capacity + coulombic efficiency).

`core/collect.py` already has `_shorten_legend` (24-char truncate + hover) and `_restyle` (right-hand vertical legend + margin). That is clearly not enough for this figure shape — the broken screenshot still shows a top-left legend with full untruncated names — so either restyle is failing silently, or legend labels are not coming from `trace.name` the way we assume for cellpy/plotly-express facet plots.

## Spec

- Make summary (and, if the same code path applies, cycles) figures remain readable when cell/group names are long.
- Prefer keeping the existing approach: shorten display labels, keep full identity available on hover (or equivalent), size margins so the plot area is not crushed.
- Ensure the restyle actually applies to faceted `Collection.plot` / plotly-express figures (legend placement + name truncation), or replace that strategy if PX facet legends need a different fix.
- Add a regression test with artificially long cell/group names asserting truncated legend labels and that the figure still returns usable layout (legend not left-overlapping the plot).

## Acceptance criteria

- [ ] With ≥1 cell whose name (or group label) is >> 40 characters, the Summary Plot legend does not overlap facet labels / axes / data.
- [ ] Full cell/group identity remains discoverable (hover or similar).
- [ ] Short names still look normal (no awkward truncation or huge empty margin).
- [ ] Automated test covers the long-name case on the figure-json path.
- [ ] Dark/light shell still fine; no new hard dependency on client-side Plotly layout hacks unless the server restyle cannot win.

## Out of scope

- Renaming cells in the library / journal UI.
- Upstream changes inside cellpy itself (unless a tiny adapter workaround is clearly insufficient — call that out in the plan).
- General legend UI redesign (toggle position, external HTML legend, etc.).
