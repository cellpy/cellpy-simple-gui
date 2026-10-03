# Plan — #175 missing or bad cycles not reported

## Goal

When a requested cycle is absent from (or unreadable in) a cell, the cell
explorer must say so — in compare mode and in the single-cell view — instead of
silently dropping the curve, or showing a blank / cryptic figure.

## What happens today (reproduced against the running server)

| Request | Result |
| --- | --- |
| compare: `c1 [1,2]` + `c2 [50]` (c2 has 1–21) | c2 silently vanishes; two c1 curves, no message |
| compare: `c1 [400]` + `c2 [50]` | empty figure, **no traces, no text** — "nothing happened" |
| explorer: `c2 [50, 51]` (voltage) | `Could not render this plot ('cycle_num').` (cellpy `KeyError`) |
| explorer: `c2 [50]` (dQ/dV) | `Could not render this plot ('DataFrame' object has no attribute 'cycle').` |
| explorer: `c2 [1, 50]` | cycle 1 drawn, 50 silently dropped |

Two silent drops happen before the server even sees the request: `parseCycleList`
in `app.js` clamps every pick to the cell's `[min, max]`, so an out-of-range
cycle yields an empty pick, and `compare_collection` discards empty picks.
Gaps inside the range (and corrupted cycles that collect to zero rows) are only
knowable server-side, after `restrict_to_cycle_pairs`.

## Constraints

- Core stays pure (no FastAPI); only `collect.py` / `cellpy_adapter.py` touch cellpy.
- Figures still come from `Collection.plot` + restyle; the report must not change
  what *is* drawn, only add a message.
- Figure endpoints keep returning Plotly figure JSON (no envelope change):
  the message travels in `layout.meta.warnings` (Plotly's free-form `meta`),
  and in the empty-figure text when nothing can be drawn.
- Export parity (#169): the compare CSV keeps exporting whatever rows exist;
  when nothing exists its 400 message explains *why* instead of "Pick one or
  more cycles to export."
- Keep the 40-cycles-per-pick / 80-curves caps.

### Prior art

- `collect.restrict_to_cycle_pairs` / `batch_keys` (#169) — the frame already
  carries `cell` + `cycle_num|cycle`; a sibling `present_cycle_pairs(collection)`
  mirrors it to learn which requested pairs survived.
- `plotting.summary_figure` + `collect.missing_summary_columns` (#97) — the
  precedent for "say what is missing rather than render a blank chart"; reuse
  `_empty_figure_json` for the all-missing case.
- `cellpy_adapter.cycle_numbers(cell)` — already backs `/api/cells/{id}/cycles`;
  gives the authoritative per-cell cycle list for the pre-check.
- `app.js` `notify()` toasts exist, but they vanish after 5 s; an inline note
  bound to the explorer pane is the better fit (toast kept out).
- Toolbox: nothing applicable (`00-tools/` index empty). Graph report god nodes
  are minified JS symbols — not useful here.

## Approach

### 1. Core — a small, pure cycle report (`core/cycle_report.py`, new)

```python
@dataclass(frozen=True)
class CycleReport:
    cell: str                 # display label (batch key)
    missing: tuple[int, ...]  # requested, not in cell.get_cycle_numbers()
    unreadable: tuple[int, ...]  # in cycle_numbers, but produced no rows
    available: tuple[int, int] | None  # (min, max) of the cell's cycles
    def message(self) -> str: ...
def compress_ranges(nums) -> str          # [22,23,24,30] -> "22–24, 30"
def build_reports(requested, available, present) -> list[CycleReport]
```

`message()` reads e.g.
`20231115_SUMBATSP2_GC2_20_cc_01: cycles 22–24, 50 not in data (has 1–21)` or
`…: cycle 7 could not be read`. `requested` is `{label: [cycles]}`,
`available` `{label: set(cycle_numbers)}`, `present` the `(label, cycle)` pairs
found in the collected frame.

### 2. `collect.py`

- `present_cycle_pairs(collection) -> set[tuple[str, int]]` — unique
  `(cell, cycle_col)` from `collection.data` (same `_CYCLE_COLUMNS` probe as
  `restrict_to_cycle_pairs`; empty set when columns are absent, with the same
  warning).
- `figure_json(..., warnings: list[str] | None = None)` — when given, sets
  `fig.update_layout(meta={"warnings": [...]})` after restyle. The
  `_empty_figure_json` helper gains the same optional `warnings` so the UI reads
  one place.

### 3. `plotting.py`

- `compare_collection(picks, spec)` → returns `(collection | None, reports)`:
  1. pre-check each pick against `cycle_numbers(rec.cell)`; split into
     existing vs missing cycles; drop picks whose cycles all miss **from the
     collect call only** (they still get a report);
  2. if no pick has an existing cycle → `(None, reports)` (never call cellpy
     with nothing — that is the `KeyError('cycle_num')` path);
  3. collect the union of *existing* cycles, `restrict_to_cycle_pairs`, then
     `present_cycle_pairs` → unreadable = existing − present;
  4. `reports = build_reports(...)`.
- `compare_figure`: `None` collection → `_empty_figure_json("Nothing to draw — " + "; ".join(messages))`
  (falls back to the current prompt when there are no reports, i.e. no cycles
  picked at all). Otherwise `figure_json(..., warnings=messages)`.
- Single-cell explorer (`cycles_figure` when `spec.cell_id` is set, `ica_figure`,
  `dva_figure`): same pre/post check through one helper
  `_single_cell_report(record, cycles, collection)`; all-missing →
  explanatory empty figure; partial → `warnings`. The Cycles **tab** (several
  selected cells, shared cycle list) only gets the all-missing guard ("none of
  the selected cells has cycles 50–51"); per-cell gaps there are expected and
  not reported.
- `export.compare_export`: uses the new tuple; when `collection is None`,
  `ValueError("Nothing to export — " + messages)` → existing 400 path.

### 4. UI (`app.js`, `index.html`, `app.css`)

- `parseCycleList(text, limit=40)` stops clamping to `[min, max]`; it only
  drops `< 1` and caps at 40 so out-of-range cycles reach the server and are
  reported uniformly. `pick.min/max` stay — shown as the cycles input's
  `placeholder`/`title` (`1–21`) so the user sees the cell's range up front.
- `cell.notes = []` state; `_plotCellFigure` sets
  `this.cell.notes = fig.layout?.meta?.warnings ?? []` on both the compare and
  single-cell branches (cleared when a figure has none).
- Template: `<div class="plot-note" role="status" x-show="cell.notes.length">`
  above `#cellChart`, one line per note. CSS: compact warning-tinted strip
  using existing theme tokens.
- `test_index_alpine_state_is_defined` picks up `cell.notes` from the state
  object automatically.

### 5. Docs

- `docs/guides/03-plotting.md`: short "Missing cycles are reported" note in the
  compare section + explorer section.
- `.issueflows/04-designs-and-guides/compare-cells.md`: addendum (transport via
  `layout.meta.warnings`, why no clamping client-side).
- `CELLPY_PAINPOINTS.md` §37: `collect_cycles`/`collect_ica` raise
  `KeyError('cycle_num')` / `AttributeError('cycle')` instead of returning an
  empty frame when none of the requested cycles exist.
- Regenerate `llms.txt` / `llms-full.txt` (`uv run tools/gen_llms_txt.py`).

## Files to touch

| Path | Change |
| --- | --- |
| `src/cellpy_simple_gui/core/cycle_report.py` | new: `CycleReport`, `compress_ranges`, `build_reports` |
| `src/cellpy_simple_gui/core/collect.py` | `present_cycle_pairs`; `warnings` kwarg on `figure_json` / `_empty_figure_json` |
| `src/cellpy_simple_gui/core/plotting.py` | `compare_collection` → `(collection, reports)`; reports in `compare_figure`, `cycles_figure`, `ica_figure`, `dva_figure` |
| `src/cellpy_simple_gui/core/export.py` | adapt `compare_export` to the tuple; explanatory `ValueError` |
| `src/cellpy_simple_gui/web/static/js/app.js` | `parseCycleList` no range clamp; `cell.notes`; read `layout.meta.warnings` |
| `src/cellpy_simple_gui/web/templates/index.html` | `.plot-note` strip above `#cellChart`; placeholder on pick cycles input |
| `src/cellpy_simple_gui/web/static/css/app.css` | `.plot-note` |
| `tests/test_compare.py` | partial-missing → warning names cell + cycle, other cell still drawn; all-missing → explanatory empty figure (no "Could not render"); export 400 message; `present_cycle_pairs` |
| `tests/test_core.py` | `cycle_report` unit tests (`compress_ranges`, missing vs unreadable split via a stub frame); single-cell explorer missing-cycle report |
| `tests/test_api.py` | `/api/plots/cycles` with `cell_id` + absent cycle → `layout.meta.warnings`, never "Could not render" |
| `docs/guides/03-plotting.md`, `CELLPY_PAINPOINTS.md`, `.issueflows/04-designs-and-guides/compare-cells.md`, `llms*.txt` | docs as above |

## Test strategy

- `uv run pytest` (currently 337 passed, 7 skipped) — new tests as listed;
  compare/API ones marked `@pytest.mark.essential` like their #169 siblings.
- Manual: against `CSG_TOKEN=devtoken169 uv run cellpy-simple-gui --server --no-open --port 8577`
  with both demo cells loaded, re-run the five reproduction requests above via
  `curl`, then a browser walkthrough (compare mode, type `50` for the 21-cycle
  cell → note appears; type `400` for both → explanatory empty figure) recorded
  to `/opt/cursor/artifacts/`.

## Open questions

1. **Message placement** — plan is an inline note above the chart (persistent)
   plus the text inside the empty figure when nothing draws. Alternative: also
   stamp the note as a figure annotation so static PNG/SVG exports carry it; I
   left that out to avoid colliding with cellpy's facet strips/legend. Say so if
   you want it in the figure too.
2. **Compare CSV with partial data** — exports the rows that exist, silently
   (CSV has nowhere to put a warning). Could add an `X-CSG-Warnings` response
   header later; out of scope here unless you want it.
3. **Cycles tab** — only the "no selected cell has any of these cycles" guard;
   per-cell gaps across several cells stay unreported (expected noise). OK?
