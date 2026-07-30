# Plan — Issue #3: Manage cells in an expanded editor

## Goal

Keep the sidebar Cells list as a compact overview, and add a **Manage cells** modal with a dense editable table so ≥20 cells can be selected, renamed, grouped, mass-edited, and removed without fighting the narrow card list.

## Constraints

- Reuse existing journal patch semantics (`POST /api/cells/{id}/update` via `updateCell`, plus `selectAll` / `removeCell` / `clearAll`). No new persistence model.
- Ship **one** expanded chrome: modal **or** drawer **or** resizable sidebar — not combinations.
- Out of scope: journal Excel import/export, virtualization, plot issues #1/#2.
- Frontend is Alpine + Jinja + CSS only (no JS test runner); backend changes only if needed.
- Themes (dark/light) and both desktop / `--server` must work; Esc closes the expanded UI.

### Prior art

- Sidebar cell cards + actions in [`index.html`](../../src/cellpy_simple_gui/web/templates/index.html) (`updateCell` / `selectAll` / `clearAll` / `removeCell`).
- Client helpers in [`app.js`](../../src/cellpy_simple_gui/web/static/js/app.js) (`updateCell` already refreshes `this.cells` from `state`).
- API already accepts `mass` on [`JournalRowUpdate`](../../src/cellpy_simple_gui/core/models.py); [`library.update`](../../src/cellpy_simple_gui/core/library.py) applies it via `adapter.set_mass`.
- Cell-list styles in [`app.css`](../../src/cellpy_simple_gui/web/static/css/app.css) (`.celllist` / `.cell-card`); **no existing modal/drawer pattern**.
- API coverage: `tests/test_api.py::test_edit_cell` (label/group/selected); mass path untested in API.
- Toolbox (`.issueflows/00-tools/`): empty. Graphify report: absent.

## Approach

### Chrome decision: **centered modal** (not drawer / not resizable sidebar)

- **Why modal:** gives a wide table without reshaping the fixed sidebar/main layout; Esc + backdrop close match acceptance criteria; Alpine `x-show` / `@keydown.escape.window` is enough — no resize state.
- **Reject drawer:** slides over the plot (primary work surface) with weaker “focus this task then dismiss” affordance for the same cost.
- **Reject resizable sidebar:** still fights a vertical card metaphor; hard to get a real multi-column table; more CSS/layout risk for less gain.

Modal size: ~`min(1100px, 94vw)` × ~`min(80vh, 720px)`, scrollable body, themed with existing CSS variables (`--panel`, `--line`, `--accent`, etc.).

### UX

1. Sidebar **Cells** panel head gains a **Manage** (or “Expand”) mini-button when `cells.length > 0`. Sidebar cards stay as today (overview + quick edits).
2. Modal title “Manage cells”; toolbar: **all / none / clear** (same handlers), **filter** text input (substring on `label`), **sort** select (`group`, `name`, default library order), **select group** number + button (client-side: `updateCell` selected=true for matching group — sequential awaits OK for typical sizes).
3. Dense HTML `<table>` rows for `filteredSortedCells` (Alpine getter):
   - checkbox → `updateCell(id, {selected})`
   - color swatch (read-only)
   - label input → `{label}`
   - group number → `{group}`
   - mass number (mg) → `{mass}` (API already supports)
   - cycles text (read-only `n_cycles`)
   - remove → `removeCell`
4. Close: **Esc**, backdrop click, and explicit Close button. Focus moves to the filter or first field on open when cheap (`$nextTick` + `.focus()`).
5. Sync: every edit already replaces `this.cells` from API `state`; sidebar and modal bind the same array — no extra sync layer.

### Backend

- **No new endpoints** for v1.
- Optionally extend `test_edit_cell` (or add a one-liner) to assert `mass` round-trips — small, valuable.

### Niceties in scope

| Feature | In v1? |
| --- | --- |
| Filter by name | Yes |
| Sort by group / name | Yes |
| Select-by-group | Yes (client-side) |
| Mass edit column | Yes |
| Virtualization | No |

## Files to touch

| Path | Change |
| --- | --- |
| `src/cellpy_simple_gui/web/templates/index.html` | Manage button on Cells panel; modal markup (toolbar + table) |
| `src/cellpy_simple_gui/web/static/js/app.js` | `cellsManagerOpen`, filter/sort state, getters/helpers (`filteredSortedCells`, `selectGroup`, open/close) |
| `src/cellpy_simple_gui/web/static/css/app.css` | Modal overlay, dialog, table density; dark/light via existing tokens |
| `tests/test_api.py` | Assert mass update via `/api/cells/{id}/update` |

## Test strategy

- Automated: `uv run pytest` from repo root; extend API edit test for `mass`.
- Manual (desktop + `--server`, dark + light): load ≥20 cells (or demo × repeats if needed), open Manage, edit label/group/mass/selection, remove one, all/none/clear, filter + sort, select-by-group, Esc closes, sidebar stays in sync, plot still refreshes after selection changes.

## Open questions

None blocking — chrome choice and niceties are decided above. Confirm or revise on Accept:

1. Prefer **drawer** or **resizable sidebar** instead of modal?
2. Drop **select-by-group** or **mass column** from v1?

## Scope check

Single UI feature + tiny API test; no unrelated refactors. Fits one PR. If the modal table later needs journal import/export, that stays a separate issue.
