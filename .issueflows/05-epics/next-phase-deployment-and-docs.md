# Next phase — deployment routes and app-builder documentation

Status: **planning** · Written 2026-08-10, against cellpy 2.1.2 / app `baf841d`.

Two goals for the next phase:

1. **Deployment** — a web-deployable form and an installable form.
2. **Documentation** — in-depth guidance for people building their own cellpy
   apps, where "people" includes coding agents.

The first phase made the app work and made cellpy better (27 issues filed, 25
closed). This phase is about making both *reusable by someone who is not us*.

---

## Decisions taken up front

| Question | Decision | Consequence |
|---|---|---|
| Who is on the other end of the web deployment? | **One instance per user** — self-hosted, container-per-person, or spawned | The single-tenant design **stays**. No session refactor. Work is packaging, configuration and lockdown |
| Which installable targets? | **Windows**, plus an **installer-free** `uv`/`pipx` route | No macOS signing, no Linux packaging, for now |
| How far does the agent story go? | **Docs first; MCP designed and prototyped, not shipped** | Guides land this phase; [cellpy#840](https://github.com/jepegit/cellpy/issues/840) gets a concrete proposal rather than speculation |

"One instance per user" is the load-bearing one. It means the process-global
singletons below are **acceptable**, not debt to repay now.

---

## What the current architecture already decides for us

Established by reading the code, not assumed:

**The app is single-tenant by construction.** `_LIBRARY`
(`core/library.py:296`), `_MANAGER` (`api/jobs.py:248`),
`_active_project_config` (`core/cellpy_config.py`) and `_INSTRUMENTS_CACHE` are
process-global. Two browsers hitting one process share one cell library, one job
queue and one cellpy config session. Fine for one-instance-per-user; fatal for a
shared URL. Anything that later wants multi-tenancy starts here.

**Server-side paths are a real exposure.** `/load/files` takes paths and globs,
`/projects/open` takes a path, `/system/pick` and `/system/save` return and write
host paths. On loopback that is the entire point of a desktop app. Reachable
over a network it is arbitrary filesystem read and write, gated only by a
per-launch token. This must be closed before the app is served anywhere, even
for a single user, because the blast radius is the *host*, not the app.

**`pywebview` is a hard dependency but a lazy import.** `import webview` only
ever happens inside functions (`desktop.py:84`, three sites in
`api/routers/system.py`), and `__main__.py` imports `.desktop` only in the
desktop branch. Moving it to an extra is a packaging change, not a refactor.

**`data_dir` is hardcoded** to `Path.home()/.cellpy_simple_gui` as a property on
`Settings`, not a setting. Containers need it configurable. cellpy has its own
directories too (config file, example-data cache), which the image must place
deliberately rather than inherit from `$HOME`.

**The install is 769 MB across 300 packages.** cellpy pulls pandas, polars and
pytables; add plotly and optionally kaleido. This sizes both the container image
and the Windows bundle, and makes "what can we leave out" a real question rather
than a micro-optimisation.

**cellpy discovers instrument loaders at runtime.**
`readers/instruments/configurations/__init__.py:145` builds module names as
strings and calls `import_module`. PyInstaller's static analysis cannot follow
that, so a naïve freeze produces an app whose instrument list is empty or
partial — and it fails at *use* time, not build time. This is the single biggest
technical risk in the phase.

---

## Milestone 1 — Headless-ready

Prerequisite for everything else. Small, mostly mechanical, except the third.

**M1.1 · Move `pywebview` to a `[desktop]` extra.**
Imports are already lazy; the work is `pyproject.toml`, the `run` helpers, and a
test that `--server` starts with `webview` absent (simulate via an import hook
rather than a second venv). Removes GUI libraries from server images.

**M1.2 · Make paths configurable.**
`CSG_DATA_DIR` as a real setting. Decide and document where cellpy's own config
and example-data cache live in a container. The existing config-diagnostics
panel already answers "where is cellpy reading from?", which makes this
verifiable from inside the running app.

**M1.3 · Close the server-path surface.** *(security-relevant)*
Introduce an explicit local-vs-served mode. Served mode: path-taking endpoints
refuse absolute paths and resolve only within `data_dir`; native pickers are
already disabled off-desktop; browser upload replaces "paste a path". Local mode
keeps today's behaviour, which is what makes the desktop app pleasant.
Needs tests for traversal (`..`, symlinks, UNC/drive-letter on Windows) — the
kind of thing that must be tested rather than reasoned about.

---

## Milestone 2 — Two ways to run it

**M2.1 · Container image.**
Multi-stage, uv-based, non-root, data dir as a volume, healthcheck. Publish to
GHCR from a tagged workflow. Document that the per-launch token is *not* an
authentication system: put it behind a reverse proxy with TLS and real auth, or
keep it on a trusted network. Being explicit about this is part of shipping it.

**M2.2 · PyInstaller spike.** ← *do this first in the milestone*
Resolve the dynamic-import problem before building anything on top. Likely
`--collect-submodules cellpy.readers.instruments` plus hidden imports for the
loaders; verify by *loading a real `.res` and a Maccor file from the frozen
build*, not by checking the app starts. If this cannot be made reliable, the
installer-free route becomes the primary answer and the .exe is dropped — better
to learn that in a day than after building an installer around it.

**M2.3 · Windows installer.**
Inno Setup around the PyInstaller output. WebView2 is present on Win10/11; add
the evergreen bootstrapper as fallback. Decide on kaleido (large; figure export
degrades gracefully without it). Flag SmartScreen: unsigned binaries warn on
first run, and the fix is a code-signing certificate, which is a purchasing
decision, not a technical one.

**M2.4 · Installer-free route.**
`uv tool install cellpy-simple-gui` / `uvx`. Prerequisite: **publish to PyPI**,
which needs the name and an owning account — an organisational decision to make
early, since M2.4 is blocked until it lands. Smaller download, needs network and
a Python at install time.

**M2.5 · Release CI.**
On tag: build the exe, build and push the image, smoke-test both (start, load a
demo cell, render one figure), attach artifacts to the release.

---

## Milestone 3 — Build your own cellpy app

The audience is human programmers *and* agents. They want different shapes of
the same knowledge, so the plan produces both from one source of truth.

**M3.1 · A minimal starter app.**
~250 lines: load cells → collect → plot → export, and nothing else. This app is
now too large to serve as a starting template — that is a good problem, but it
means the reference implementation and the *starting point* should be different
artifacts. Small enough for a human to read in a sitting and for an agent to
hold in context alongside the task.

**M3.2 · Task-shaped guides.**
Organised by what someone is trying to do, not by module:

- getting cells into memory (`get`, files, journals, raw ingestion)
- turning cells into a `Collection` (`from_cells`, the `collect_*` family)
- plotting a collection (the registry, `summary_options`, `entry_point`, layouts
  vs kinds — including the `film` trap from §29)
- exporting data and figures
- configuration (the 2.1.2 layered stack — genuinely under-documented, and we
  now understand it well)
- process state and threading (the singletons; cellpy's process-global config;
  what is safe to call from a worker thread)
- what cellpy will and will not do for you — distilled from
  `cellpy-delegation-inventory.md`, which is already exactly this document for
  our own app

**M3.3 · Machine-readable layer.**
`llms.txt` + a distilled API-surface reference: the ~40 calls that matter, with
signatures and one-line semantics, so an agent does not have to grep
`site-packages` to find `family.summary_options`. Plus a Claude Skill packaging
the guides. The test of this layer is empirical: give an agent a cold context
and the docs, and see whether it can build a working plot without reading cellpy
source.

**M3.4 · MCP design + prototype for [cellpy#840](https://github.com/jepegit/cellpy/issues/840).**
Scoped, not shipped. Design doc covering the tool surface (load, collect, plot,
export, describe-registry), and the two hard parts: **state** — an MCP server is
long-lived and multi-client, which walks straight into the process-global config
problem that produced cellpy#850 — and **file access**, the same exposure as
M1.3 in a different costume. A small prototype to prove or disprove the design,
then post it to #840 as a concrete proposal.

---

## Risks

| Risk | Milestone | Handling |
|---|---|---|
| PyInstaller cannot follow cellpy's dynamic loader imports | M2.2 | Spike first; verify by loading real instrument files from the frozen build; drop the .exe route if it cannot be made reliable |
| PyPI name not available / no owning account | M2.4 | Decide early — it blocks the installer-free route entirely |
| Unsigned Windows binary triggers SmartScreen | M2.3 | Document; certificate is a purchasing decision |
| 769 MB dependency tree inflates image and bundle | M2.1, M2.3 | Trim extras deliberately; measure and record, do not guess |
| Serving the app exposes host filesystem | M1.3 | Treat as security work: explicit mode, root-jail, traversal tests |
| Docs drift from the code, as they always do | M3 | Prefer generated/derived content; keep the delegation inventory as the living source it already is |

---

## Sequencing

M1 → M2 → M3 by dependency, but M3 needs no deployment work and can start in
parallel whenever there is appetite. Within M2, **M2.2 before M2.3**, and M2.4 is
blocked on the PyPI decision.

The first thing worth doing is **M2.2, the PyInstaller spike** — out of order,
because it is the only item that can invalidate a whole route, and it is cheap
to answer.
