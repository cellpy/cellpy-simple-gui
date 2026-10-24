# Plan — #184 update plots when the Manage cells modal closes

## Goal

Editing in the **Manage cells** modal must not trigger a plot round-trip per
edit; the current tab's figure refreshes **once, when the modal closes**. And
no figure may keep re-rendering after the user is done: a plot response that
has been superseded by a newer request is dropped, never drawn.

## What happens today

- Every edit in the modal (`updateCell` / `selectAll` / `removeCell`) calls
  `replotCurrent()` straight away. Each is a server round-trip; the modal is
  still covering the chart, so the work is invisible and only adds latency.
- Nothing serialises or de-duplicates those requests. Each response arrives
  later and calls `Plotly.react` on arrival, so after N quick edits the chart
  visibly redraws N times, long after the last edit (and after the modal has
  closed). `_withPlotBusy` also clears the spinner when the *first* response
  lands, while later ones are still in flight.

## Approach (front-end only, `app.js` + modal markup)

1. **Defer while the modal is open.** Route every "the library changed, redraw"
   call through one helper, `_replotAfterEdit()`. While `cellsManagerOpen` it
   only sets `_replotOnClose = true`; otherwise it replots as before (sidebar
   edits stay immediate). `closeCellsManager()` replots once if the flag is set.
   `clearAll()` closes the modal itself and replots directly (unchanged).
2. **Drop stale responses.** Per chart (`summary` / `cycles` / `cell`) keep a
   request sequence number. Each plot call takes the next number before the
   fetch and, when the response arrives, only draws if it is still the latest.
   Superseded responses are discarded without touching Plotly. Busy state
   becomes a counter so the spinner stays up until the *last* in-flight request
   for that chart settles.
3. A one-line note in the modal footer: "Plots refresh when this dialog
   closes." so the deferred behaviour is not mistaken for a broken edit.

## Files to touch

- `src/cellpy_simple_gui/web/static/js/app.js`
- `src/cellpy_simple_gui/web/templates/index.html` (modal footer note)
- `tests/test_gui_playwright.py` — e2e: edits in the modal issue no
  `/api/plots/*` requests; one is issued on close (skips without Playwright,
  like the existing e2e tests).
- `.issueflows/04-designs-and-guides/manage-cells-modal.md` — behaviour note.

## Test strategy

- Playwright e2e (local): count `/api/plots/summary` requests while editing in
  the modal (expect 0) and after Close (expect 1).
- Manual browser walkthrough in `--server` mode (recording).
- Full `uv run pytest` green; essential CI check green.
