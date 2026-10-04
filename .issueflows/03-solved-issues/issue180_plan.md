# Plan — #180 make smarter caching

## Goal

Stop rebuilding a plot from scratch when the user switches tabs or changes
colours, and never serve a figure after the loaded cells, selection, groups,
or labels have changed. The rules for what is reused and what is thrown away
live in one policy, so a later change of those rules does not require a new
cache.

## Constraints

- Single-user process. The in-memory `Library` is the source of truth
  (`core/library.py`). Cache lives in that same process and dies with it.
- No new dependencies. No disk cache. No plugin registry.
- Colour, group shade, and shade spread are applied after `collection.plot`
  in `collect.figure_json` → `_restyle` → `_apply_colorway`. Figure theme is
  also passed into `collection.plot` via `_inject_app_chrome`, and into the
  shade fan, so a theme change still replots.
- Tab buttons always call `plotSummary` / `ensureCyclesBounds` /
  `ensureCellSelected` (`web/templates/index.html`). The chart DOM stays
  mounted (`x-show`). `_fetchFigure` only drops out-of-order responses
  (#184); it does not reuse a figure.
- Export and the HTTP shape stay the same: plot routes still return Plotly
  JSON. Export calls the same builders, so it hits the same keys.

### Prior art

- Toolbox: none (`00-tools/README.md` index is empty).
- Graph: `graphify-out/` is not in this worktree. Skipped.
- `config.get_settings` — `@lru_cache` for settings, not plots. Leave it.
- `cellpy_adapter._INSTRUMENTS_CACHE` — instrument list. Unrelated. Leave it.
- `Library` mutators (`add_cell`, `restore_cell`, `update`, `remove`,
  `clear`, `set_selection`, `set_group_label`) are the only places cells
  enter or change. `mark_saved` is provenance only.
- `collect.summary_collection`, `cycles_collection`, `ica_collection`,
  `dva_collection` plus `figure_json` are the expensive path. Colour is not
  part of collect.

## Approach

One module, `core/plot_cache.py`, owns the policy and the memos. Plot code
asks it for a key and a slot. It does not decide for itself which fields are
cheap or which edits invalidate.

### Policy (the only place behaviour is chosen)

```text
COSMETIC = {color_scheme, group_shade, shade_spread}
BUMPS    = {add_cell, restore_cell, update, remove, clear,
            set_selection, set_group_label}
QUIET    = {mark_saved}
MAX_ENTRIES = 8
enabled  = env CSG_PLOT_CACHE is not "0"
```

A field absent from `COSMETIC` is structural. A new spec field recomputes
until someone adds it to `COSMETIC` on purpose. That default is the safe one.

`enabled` is read on each lookup. `CSG_PLOT_CACHE=0` forces a miss and stores
nothing. Builders also take `use_cache=True` so one caller can opt out
without turning the cache off for the process.

### What is stored

1. **Revision.** `Library.revision` starts at 0. Mutators in `BUMPS` call
   `_touch()` under the existing lock. `QUIET` does not. `/api/state`
   includes `revision`. One counter for now: any listed edit drops both
   memos. `_touch()` is the only bump, so a future writer has one call to
   make.

2. **Collect memo.** Key is `(revision, helper name, canonical args)`. Args
   are record ids in order plus the collect kwargs, not the cell objects.
   A hit returns the same collection. Used by `summary_collection`,
   `cycles_collection`, `ica_collection`, `dva_collection`.

3. **Pre-style figure memo.** Inside `figure_json`, `raw_figure_json`, and
   `cycle_info_figure_json`. The key is revision plus every argument except
   the names in `COSMETIC`. The stored figure is a copy taken **before**
   `_restyle`. A hit deep-copies that snapshot and runs `_restyle` only, so
   a colour change cannot paint the stored figure. Theme, ranges, spread,
   overlay, and plot type stay in the key.

4. **Browser memo.** Each chart remembers the last figure plus `revision`
   and the full request body. Tab switches draw it and skip the POST when
   both match. The browser does **not** keep its own copy of `COSMETIC`:
   any body change, including colour, still goes to the server, and the
   server policy decides whether that is a restyle or a rebuild. A new
   `revision` from `_applyState` clears the memo before the follow-up plot.
   `_plotSeq` still discards a late response.

On revision change, drop server entries whose revision does not match.
Cap each memo at `MAX_ENTRIES` (insertion order). Tests that share a
library call `plot_cache.clear()` from a fixture.

### Later changes, and the knob for each

| What changed | Edit |
| --- | --- |
| A restyle field starts affecting `collection.plot` | Remove it from `COSMETIC` |
| A plot argument becomes restyle-only | Add it to `COSMETIC`, and apply it only after the snapshot |
| Cache serves a stale figure | `CSG_PLOT_CACHE=0`, or `use_cache=False` on that call |
| Figures use too much memory | `MAX_ENTRIES` |
| A new Library writer appears | Call `_touch()` from it, and add the name to `BUMPS` |
| Label or selection edits should keep collected frames | Split `revision` into a data counter and a view counter inside `plot_cache.py`. Collect keys use the data counter. Figure keys use the view counter. Call sites stay `_touch()` |
| A live reload mutates a cell outside `Library` | That path calls `_touch()` |
| One chart should restyle in the browser | New work. The browser memo stays a full-body skip until then |

## Files to touch

- `src/cellpy_simple_gui/core/plot_cache.py` — new. Policy constants, both
  memos, `clear()`, `enabled()`.
- `src/cellpy_simple_gui/core/library.py` — `revision`, `_touch()` from the
  `BUMPS` methods only.
- `src/cellpy_simple_gui/core/collect.py` — collection helpers and the three
  figure helpers take their keys from the policy. Snapshot before `_restyle`.
- `src/cellpy_simple_gui/api/routers/cells.py` — `revision` on `_state()`.
- `src/cellpy_simple_gui/web/static/js/app.js` — per-chart memo keyed by
  revision and the full body.
- `tests/test_plot_cache.py` — new. See test strategy.
- `.issueflows/04-designs-and-guides/plot-cache.md` — the policy table and
  the "later changes" table, so the next edit starts there.

## Test strategy

`uv run pytest tests/test_plot_cache.py tests/test_core.py tests/test_api.py`

- Same summary spec twice: `summary_collection` and `collection.plot` run
  once. Second call returns the same JSON.
- Changing only a `COSMETIC` field does not call collect or `plot` again,
  and the trace colours differ. A second colour does not alter the figure
  returned for the first colour (snapshot was copied).
- Changing a structural field (`plot_type`, `figure_theme`, `basis`) misses.
- Each `BUMPS` method increases `revision`. `mark_saved` does not.
- With `CSG_PLOT_CACHE=0`, the second identical call misses.
- `/api/state` includes `revision`, and it increases after a cell edit.

## Open questions

- None. One revision counter until a measured case needs the data/view
  split. The split is confined to `plot_cache.py`.
