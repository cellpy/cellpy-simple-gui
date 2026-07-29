# Multi-root workspace — cellpyapp

Editor workspace: `cellpyapp-workspace.code-workspace` under
`C:\scripting\cellpyapp-workspace\`.

## Members

| Folder | GitHub | issue-flow scaffold | Role |
|---|---|---|---|
| `cellpy-simple-gui` | [cellpy/cellpy-simple-gui](https://github.com/cellpy/cellpy-simple-gui) | **Yes** (this tree) | Active desktop GUI MVP — default focus for new work |
| `cell_processor_app` | [jepegit/cell_processor_app](https://github.com/jepegit/cell_processor_app) | No | Legacy Streamlit demo (reference) |
| `cellpy_streamlit_installer` | [jepegit/cellpy_streamlit_installer](https://github.com/jepegit/cellpy_streamlit_installer) | No | Packaging / InnoSetup reference for the Windows installer |

Workspace-root files that are **not** a git repo: `cellprocessor_v2_design.md`
(design draft), `assets/`, the `.code-workspace` file itself. Design content for
agents is mirrored into this repo under
`.issueflows/04-designs-and-guides/cellprocessor-v2-design.md`.

## Default for lifecycle commands

Until an `issueflow-workspace.toml` exists at the workspace root, **only this
repo** has `.issueflows/`, so `issue-flow agent resolve` should land here when
a single scaffold is visible. Still:

- Prefer explicit hints: `repo:cellpy-simple-gui` or
  `root:C:\scripting\cellpyapp-workspace\cellpy-simple-gui`.
- Never let `git` / `gh` infer the repo from a random cwd.
- Most `gh` commands: `--repo cellpy/cellpy-simple-gui`. Exception:
  `gh repo view cellpy/cellpy-simple-gui …` (positional; no `--repo`).

Optional registry (create from the workspace parent when ready):

```bash
# from C:\scripting\cellpyapp-workspace
issue-flow workspace init --default cellpy-simple-gui
```

```toml
[workspace]
default = "cellpy-simple-gui"
members = ["cellpy-simple-gui", "cell_processor_app", "cellpy_streamlit_installer"]
```

Only scaffolded members participate in lifecycle resolution. Sibling repos
without `.issueflows/` are reference checkouts — do not invent issue tracking
there unless someone runs `issue-flow init` on purpose.

## Toolchain disambiguation

| Repo | How to run Python / tests |
|---|---|
| `cellpy-simple-gui` | `cd cellpy-simple-gui && uv sync --extra dev && uv run pytest` |
| `cell_processor_app` | Follow *that* repo's README / conda or venv — do not `uv run` from the workspace parent |
| `cellpy_streamlit_installer` | Installer scripts / InnoSetup under that tree |

Running `pytest` or `uv run` from the workspace parent can accidentally collect
or confuse sibling packages. Always `-C` / `cd` into the target repo first.

## Cross-repo guidance

- **Product work** → `cellpy-simple-gui` issues and PRs.
- **Behaviour comparison / migration notes** → read `cell_processor_app` as
  prior art; do not "fix" it unless explicitly asked.
- **Installer epic** → implement packaging in `cellpy-simple-gui` (or a path
  that repo owns), borrowing patterns from `cellpy_streamlit_installer`.
- `/iflow-cleanup` is per-repo; after a PR merges, clean up only the repo that
  owned the branch.
