# Issue #1 plan: Fix Plotly summary legend when cell names are very long

## Goal

Make summary (and cycles) Plotly figures stay readable when cell/group legend
names are very long: truncated display labels, full identity on hover, right-hand
legend + enough margin — with a regression test on the figure-json path.

## Constraints

- Stay inside the app restyle layer (`core/collect.py`); no cellpy upstream change
  unless a tiny adapter workaround is clearly insufficient (call that out then).
- Prefer existing approach: shorten display names + hover for full identity +
  right-hand vertical legend + margin sizing. No general legend UI redesign.
- No new client-side Plotly layout hacks unless server restyle cannot win.
- Same restyle path already covers cycles via `figure_json` → `_restyle`; keep that.
- Toolchain: `uv run pytest` (do not invent a formatter gate).

### Prior art

- `collect._shorten_legend` / `collect._restyle` / `collect.figure_json` —
  [`src/cellpy_simple_gui/core/collect.py`](../../../src/cellpy_simple_gui/core/collect.py):
  existing 24-char truncate + right legend + margin; **mirror/fix in place**
  (this is the broken path).
- `plotting.summary_figure` / `cycles_figure` —
  [`src/cellpy_simple_gui/core/plotting.py`](../../../src/cellpy_simple_gui/core/plotting.py):
  thin wrappers; no legend logic here.
- `_batch` cell keys = `rec.label or rec.name or rec.id` (same file): long
  journal labels become series identities / legend names.
- Tests: [`tests/test_core.py`](../../../tests/test_core.py)
  (`test_summary_collection_and_figure`, `test_grouped_summary_renders`) —
  assert traces exist but not legend layout; **extend** with a long-name case.
- Design note: `CELLPY_PAINPOINTS.md` §11 documents app-side `_restyle` as the
  intended place for figure cosmetics — **coexist** (no theme hook in cellpy yet).
- Toolbox (`00-tools/`): none relevant. Graphify: not present.

## Approach

1. **Diagnose on a long-name figure (build-time, read-only first).**
   Build a summary figure (Capacity + CE) with ≥1 label ≫ 40 chars (and a
   group-average case if cheap). Inspect figure JSON: `data[*].name` /
   `legendgroup` / hover fields, and `layout.legend` / `margin.r`. Confirm which
   of the issue’s two hypotheses holds:
   - `_restyle` throws and the bare `except Exception: pass` swallows it, or
   - shorten only looks at `tr.name` while PX/cellpy stores the visible label
     elsewhere / legend stays at default top-left.

2. **Make legend shortening reliable (primary fix).**
   - Restructure so **name shortening always runs** even if cosmetic layout
     updates fail (today shorten lives inside the all-or-nothing `try` in
     `_restyle`).
   - Truncate every legend-facing string we find: at least `trace.name`, and
     `legendgroup` when it carries the long identity (keep shorten + display
     consistent so legend entries don’t diverge).
   - Keep `_LEGEND_NAME_LIMIT = 24` unless diagnosis shows a clear need to
     change it; short names must remain unchanged.
   - Preserve full identity for discovery: prefer a hover path that works with
     cellpy/PX `hovertemplate` (e.g. `customdata` / template tweak, or
     `hovertext` + ensuring it surfaces). Do not leave full name only on a
     field Plotly never shows.

3. **Make right-hand legend + margin stick.**
   - Keep vertical legend at `x>1`, `xanchor=left`, sized `margin.r` from the
     *displayed* (truncated) name length.
   - If PX facet defaults still win, force the legend dict after plot creation
     (same `_restyle`); only then consider a documented narrow fallback.
   - Narrow the bare `except`: cosmetics may stay best-effort, but do not
     silently skip shortening; optionally log a warning on cosmetic failure
     (no new dependency).

4. **Regression test** in `tests/test_core.py` (figure-json path):
   - Set an artificially long `label` on a loaded cell (≫ 40 chars); build
     summary figure via `plotting.summary_figure` or `collect.figure_json`.
   - Assert every non-empty `trace.name` length ≤ limit (ellipsis form OK).
   - Assert `layout.legend` is vertical / right-anchored (not default top-left
     only) and `margin.r` is large enough for the truncated labels.
   - Assert full identity remains available (hovertext / customdata / equivalent
     field chosen in step 2).
   - Keep an assertion that a short-name figure still looks normal (names
     unchanged; no huge empty margin).

5. **Out of scope stays out:** no rename UI, no external HTML legend, no cellpy
   PR unless step 1 proves app-side restyle cannot see/fix the labels.

## Files to touch

| Path | Change |
| --- | --- |
| [`src/cellpy_simple_gui/core/collect.py`](../../../src/cellpy_simple_gui/core/collect.py) | Fix `_shorten_legend` / `_restyle` (ordering, fields covered, hover, exception handling, margin/legend apply). |
| [`tests/test_core.py`](../../../tests/test_core.py) | Add long-name (and short-name sanity) regression on figure JSON. |
| `.issueflows/04-designs-and-guides/` | Only if diagnosis yields a non-obvious legend-field decision worth recording (terse note + link to #1). |

No API / frontend / model changes expected.

## Test strategy

- `uv run pytest` (full suite; project brief).
- New focused tests as above; reuse `loaded_library` / `example_cell` fixtures.
- Manual spot-check in desktop or `--server` only if automated layout asserts
  leave doubt (dark/light shell already untouched by this path).

## Open questions

None blocking — recommended defaults above (fix in `_restyle`/`_shorten_legend`,
keep limit 24, cover cycles via shared path, no client hacks first). Confirm to
proceed, or revise if you want a different truncate length / hover strategy.
