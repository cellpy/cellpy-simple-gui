# Issue #73: Job progress pane: Cancel/Dismiss overlap long status text

Source: https://github.com/cellpy/cellpy-simple-gui/issues/73

## Original issue text

## Problem / context

During long-running jobs (e.g. project save), the sidebar job/progress row shows a status message like `Saving "20240521_nor000_06_f…"` beside **Cancel** / **Dismiss**. With long filenames, the buttons overlap the message instead of staying clear of the text.

The **Cells** list already handles overflow with a scrollable region (`.celllist { overflow-y: auto; … }`). A similar pattern for the job message (scroll and/or truncate within a reserved flex slot) would keep actions usable.

## Spec

- Keep **Cancel** / **Dismiss** fully visible and clickable; they must not cover the status text.
- Constrain the message area (ellipsis and/or horizontal/vertical scroll), mirroring the Cells pane overflow approach where it fits.
- Preserve the progress bar and spinner layout; no change to cancel/dismiss behaviour.

## Acceptance criteria

- [ ] With a long save/job message (long quoted filename), Cancel and Dismiss do not overlap the text.
- [ ] Status text remains readable via truncate and/or scroll within the message slot.
- [ ] Layout still works in a narrow sidebar (typical desktop width).

## Out of scope

- Changing job SSE / cancel semantics.
- Redesigning the Cells pane itself.
