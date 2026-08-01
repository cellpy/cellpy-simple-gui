# Issue #69: edit meta data

Source: https://github.com/cellpy/cellpy-simple-gui/issues/69

## Original issue text

A typical use case is that the user has to change some of the meta-data of a cell (mass, nominal capacity, etc). It is important for app-builders that this process is fairly straight forward. Let us add that option to our app (maybe through the cell explorer, another tab, or from the CELLS modal. Some meta data changes requires re-calculating the summaries (for example, a new nominal capacity will give different C-rates, new mass will give different gravimetric capacities etc). Make sure to report back to cellpy (through the CELLPY_PAINPOINTS.md document) if we experience pain-points in implementing it.

## Comments (curated summary)

- **Clarifications / constraints**:
  - Cells modal already has a mass field — extend/edit there rather than inventing a parallel mass UI.
  - Hard part is knowing *when* and *which parts* of the summary must be recalculated for a given meta change (parameter → dependent summary columns). Expect cellpy pain-points; may need an upstream dependency graph for meta params (e.g. `nominal_capacity` → summary columns X/Y/Z). Document findings in `CELLPY_PAINPOINTS.md`.

_Note: this section is an interpretive summary of the comment thread, not a verbatim dump. Source comments: 2, last comment by @jepegit on 2026-08-01._

