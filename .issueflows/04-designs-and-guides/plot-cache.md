# Plot cache

Issue #180. The rules live in `src/cellpy_simple_gui/core/plot_cache.py`.
Plot code asks that module for a slot. It does not decide what is cheap.

## Policy

| Constant | Meaning |
| --- | --- |
| `COSMETIC` | `color_scheme`, `group_shade`, `shade_spread`. Restyle only. A field not listed here rebuilds the collection and the figure. |
| `BUMPS` | Library methods that call `_touch`: add, restore, update, remove, clear, selection, group label. |
| `QUIET` | `mark_saved`. Provenance, not a plot change. |
| `MAX_ENTRIES` | 8 per memo. |
| `CSG_PLOT_CACHE=0` | Miss and store nothing. `use_cache=False` does that for one call. |

One `Library.revision` for now. `/api/state` sends it. The browser memo key is
that revision plus the full request body, so a colour change still reaches
the server. The server then restyles a stored pre-`_restyle` figure.

The stored figure is cloned before it is saved and cloned again on a hit, so
a restyle cannot paint the entry. The clone is a Plotly JSON round-trip.
``copy.deepcopy`` shares the figure's buffers, so a restyle would paint the
stored copy.

``select_ica_direction`` copies the collection before it replaces ``data``.
The collect memo returns the same object, and an in-place filter would leave
the next export of the other half-cycle empty.

## When the behaviour has to change

| What changed | Edit |
| --- | --- |
| A restyle field starts affecting `collection.plot` | Remove it from `COSMETIC` |
| A plot argument becomes restyle-only | Add it to `COSMETIC`, and apply it only after the snapshot |
| A stale figure shows up | `CSG_PLOT_CACHE=0`, or `use_cache=False` on that call |
| Figures use too much memory | `MAX_ENTRIES` |
| A new Library writer appears | Call `_touch()` and add the name to `BUMPS` |
| Label or selection edits should keep collected frames | Split `revision` into a data counter and a view counter inside `plot_cache.py`. Collect keys use the data counter. Figure keys use the view counter. |
| A live reload mutates a cell outside `Library` | That path calls `_touch()` |
