# Summary plot legend + long cell names (#1)

## Context

Facetted `Collection.plot` / Plotly Express summary figures put series identity
on `trace.name` (and a short id on `legendgroup`). Right-side facet strip
annotations sit at `x≈0.98` (`textangle=90`) and compete with a right-hand
legend for the same margin.

## Decision

- Truncate legend-facing `name` (and long non-numeric `legendgroup`) in
  `core/collect.py::_shorten_legend` **before** cosmetic `_restyle` layout work,
  so a cosmetics failure cannot leave full names in place.
- Keep full identity on hover via the existing PX `hovertemplate` literal prefix
  (do not rely on `hovertext` when a template is set — Plotly ignores it).
- Reserve extra right margin for facet strips + truncated legend width; tidy
  `variable=…` strip text to the bare column id.

## Alternatives considered

- Client-side Plotly layout hacks — rejected unless server restyle cannot win.
- Moving the legend below the plot — more invasive; right-hand vertical legend
  kept as the app default.
