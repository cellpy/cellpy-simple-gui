# Job Cancel / Dismiss

From issue #47 (`/iflow-fix`).

## Context

Long jobs (especially batch-journal load via cellpy) can block cooperatively
only between steps. A stuck spinner left the UI unusable.

## Decision

- **Cancel** — `POST /api/jobs/{id}/cancel` sets the cooperative cancel event;
  load loops honour it via `progress.update` / `check_cancel`.
- **Dismiss** — closes the SSE stream and clears the spinner immediately so the
  user can keep working; still best-effort cancels the backend job.
- Cellpy calls that block mid-call cannot be interrupted; Dismiss is the escape
  hatch for that case.
