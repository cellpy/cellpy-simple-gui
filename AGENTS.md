<!-- BEGIN issue-flow (managed: do not edit this block) -->
# Issue-flow

This project tracks GitHub issues with issue-flow. Each `iflow-*` skill holds its own instructions; read a skill only when it is invoked.

## Running Python

Follow the project's documented toolchain (README, `AGENTS.md`, `pyproject.toml`, `environment.yml`, CI). Never call bare `python`: use the project's runner (`uv run …` by default, `conda run -n <env> …` for conda projects, `poetry run …` for poetry). In a uv project, manage dependencies with `uv add` / `uv remove` / `uv sync`, not `pip`.

## Tracking layout

Under `.issueflows/`:

- `00-tools/` — reusable helper scripts; `README.md` is the index. Check it before writing a one-off helper, and add useful tools back.
- `01-current-issues/` — the focus issue only: `issue<N>_original.md`, `issue<N>_plan.md`, `issue<N>_status.md`.
- `02-partly-solved-issues/` — parked work. `03-solved-issues/` — finished work.
- `04-designs-and-guides/` — durable design docs; `this-project.md` is the project brief.
- `05-epics/` — staged epic plans (`epic<N>_plan.md`).

- After each iteration, update `issue<N>_status.md` (done, current state, remaining work) with an explicit checkbox: `- [x] Done` when fully resolved, `- [ ] Done` otherwise. Other steps route files by that checkbox.
- Finished issues move to `03-solved-issues/`, unfinished ones to `02-partly-solved-issues/`.
- Before planning or building, read `04-designs-and-guides/this-project.md` if present and skim `04-designs-and-guides/` for relevant docs. Record non-trivial design decisions there (context, decision, alternatives, issue link).

## Commands

Invoke as `/iflow-<step>` or in chat as `iflow <step> [args]` (also `iflow-<step>` or `/iflow <step>`). A message that **starts with** one of these forms invokes the `iflow-<step>` skill with the trailing text as its arguments; plain `iflow` runs the dispatcher. Mid-sentence mentions are not invocations.

| Command | Purpose |
|---|---|
| `iflow` | Dispatcher: run the next of capture / plan / build / close. |
| `iflow-setup` | Get a project ready (uv, git, GitHub, scaffold). |
| `iflow-pick` | Choose an issue, branch, and capture it. |
| `iflow-plan` | Write the plan and stop for approval. |
| `iflow-build` | Implement the approved plan. |
| `iflow-pause` | Park unfinished work with resume notes. |
| `iflow-close` | Tests, bump, changelog trailers, commit, push, PR. |
| `iflow-cleanup` | After merge: default branch, pull, delete landed branches. |
| `iflow-run` | Hands-off runs under one up-front confirm. |
| `iflow-issue` | Create and shape GitHub issues. |
| `iflow-status` | Read-only overview of every issue. |
The core loop is `pick → plan → build → close → cleanup`. `/iflow` detects the focus issue's state and dispatches to the next of capture / plan / build / close; it never dispatches to any other command. Never skip the plan confirmation in `/iflow-plan` unless a hands-off mode was confirmed.

Issue labels can route `/iflow-pick`: `yolo` → `/iflow-run yolo`, `ops` → no-PR close (ops wins over yolo). A `publish` label makes `/iflow-close` bump the version and release after merge.

## Branch hygiene

- Work on an issue branch `<N>-<short-slug>`, never on the default branch.
- Before continuing a branch, run `git fetch --prune` and check ahead/behind against `origin/<default>`. PRs are **squash**-merged, so a merged branch looks "ahead" and is stale.
- After a PR merges, remind the user to run `/iflow-cleanup`. Do not run it automatically.
- An issue already under `02-partly-solved-issues/` or `03-solved-issues/` has a stale branch. Re-open it only on purpose with `/iflow-pick <N>`.

## Multi-repo workspaces

When the workspace holds several repos with their own `.issueflows/`, resolve the target repo first (`root:` / `repo:` hints, then `issue-flow agent resolve`, then the `issueflow-workspace.toml` default); ask when ambiguous. Pass `--repo <owner/repo>` to every `gh` call. Lifecycle state is per repository.

## Optional skills

- **caveman** — terse response style. Off until the user asks ("caveman", "be terse"). Off with "stop caveman" / "normal mode". Code, commits, PRs, security warnings, and destructive-action confirmations are always normal prose.
- **grill-me** — relentless one-question-at-a-time planning interview. Off until the user asks ("grill me"). Off with "stop grilling".

## Knowledge graph

If `graphify-out/GRAPH_REPORT.md` exists, skim it before grepping. Run `graphify query` / `path` / `explain` only when `graphify-out/graph.json` exists. `/iflow-status graph` rebuilds the graph; nothing runs it automatically.


<!-- END issue-flow (managed) -->

## Cursor Cloud specific instructions

This repo is a single Python desktop app (`cellpy-simple-gui`): a FastAPI backend
served inside a native `pywebview` window. Toolchain is **uv** + **Python 3.13**
(see `.python-version`, `pyproject.toml`). The update script installs `uv` (if
missing) and runs `uv sync --extra dev --extra export`, so deps are ready at
session start. Standard dev/test commands live in `README.md` and `pyproject.toml`.

- **Run headless in the cloud (no display):** always use server mode, not the
  default desktop mode. Desktop mode tries `pywebview` (needs a display) and only
  falls back to browser mode on exception.
  `uv run cellpy-simple-gui --server --no-open --port 8577`
- **API auth token:** every API route (except `/`, `/healthz`, `/static`) needs a
  per-launch token. It is random by default; set it deterministically with the
  `CSG_TOKEN` env var (prefix `CSG_`) for scripted testing, then pass
  `?token=<value>` on requests or browse `http://127.0.0.1:8577/?token=<value>`
  (the index route plants a `csg_token` cookie).
- **Only one server per port:** `pick_port` silently falls back to a random port
  if the preferred one is busy, so a stale server keeps its old random token. Kill
  the previous process by PID before restarting on the same port.
- **Hello-world / smoke flow:** load demo cells then render a summary plot.
  `POST /api/load/example {"kinds":["cellpy","rate"]}` returns a `job_id`; poll
  `GET /api/jobs/<id>` until `status == "done"`; then
  `POST /api/plots/summary {"plot_type":"capacity_ce","basis":"gravimetric"}`
  returns Plotly figure JSON. In the GUI: click **Load demo cells**.
- **First demo load needs network:** demo/example cells are downloaded once from
  the cellpy example-data repo, then cached under `~/.cellpy_simple_gui`.
- **Lint:** no separate linter/formatter is configured; `uv run pytest` (34 tests,
  core + FastAPI integration) is the check.
- **`export` extra (kaleido):** only needed for server-side static PNG/SVG/PDF
  export; not required to run or test the app.

