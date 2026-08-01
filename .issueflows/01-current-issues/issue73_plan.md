# Plan — Issue #73: Job progress Cancel/Dismiss overlap

## Goal

Keep **Cancel** / **Dismiss** fully visible and clickable when the job status
message contains a long filename, by constraining `.job-msg` overflow inside its
flex slot (truncate with ellipsis; full text via hover `title`).

## Constraints

- No change to job SSE, cancel, or dismiss behaviour (`app.js` / `api/jobs.py`).
- Preserve spinner + progress bar layout.
- Do not redesign the Cells pane.
- Prefer existing sidebar patterns (see Prior art).

### Prior art

- [`.job-row` / `.job-msg` / `.job-actions`](../../src/cellpy_simple_gui/web/static/css/app.css) —
  flex row already has `flex: 1; min-width: 0` on the message and `flex: none` on
  actions; missing overflow clamp is why text paints over the buttons.
- [`.proj-tag`](../../src/cellpy_simple_gui/web/static/css/app.css) — same ellipsis
  recipe (`overflow: hidden; text-overflow: ellipsis; white-space: nowrap`).
  **Mirror** this on `.job-msg`.
- [`.celllist`](../../src/cellpy_simple_gui/web/static/css/app.css) —
  `overflow-y: auto` for a multi-item list; less apt for a one-line status.
- Markup in [`index.html`](../../src/cellpy_simple_gui/web/templates/index.html)
  (`.job` / `.job-row` / `.job-msg` / `.job-actions`).
- Design note [job-cancel-dismiss.md](../04-designs-and-guides/job-cancel-dismiss.md)
  — semantics stay as documented; this issue is layout-only.
- Toolbox: none relevant.

## Approach

1. **CSS** — On `.job-msg`, add the `.proj-tag` overflow clamp so the flex child
   actually clips instead of overflowing into `.job-actions`. Keep
   `flex: 1; min-width: 0`. Leave `.job-actions` / `.spinner` as `flex: none`.
2. **HTML** — Bind `:title` on `.job-msg` to the same string shown in the span
   so the truncated message remains readable on hover.
3. **Smoke** — Manually (or via a short Playwright/devtools check) set a long
   `job.message` / trigger a save with a long project name and confirm buttons
   do not overlap and remain clickable in the narrow sidebar.
4. **Docs** — One-line note under job-cancel-dismiss (or a tiny sibling) that
   the message slot truncates; optional if the CSS comment is enough.

## Files to touch

| Path | Change |
| --- | --- |
| `src/cellpy_simple_gui/web/static/css/app.css` | Ellipsis / overflow on `.job-msg` |
| `src/cellpy_simple_gui/web/templates/index.html` | `:title` on `.job-msg` |
| `.issueflows/04-designs-and-guides/job-cancel-dismiss.md` | Optional one-liner on layout |
| `.issueflows/01-current-issues/issue73_status.md` | Track progress during build |

## Test strategy

- `uv run pytest` (regression; no existing unit coverage for this CSS).
- Visual/layout check: long job message → Cancel/Dismiss not overlapped,
  text truncated or scrollable, narrow sidebar still usable.
- No new automated test required unless an e2e hook is trivial; optional later.

## Open questions

None blocking — recommended default is **single-line ellipsis + `title` hover**
(mirror `.proj-tag`), not vertical scroll like `.celllist`. Say if you prefer
`overflow-x: auto` instead of (or in addition to) ellipsis.
