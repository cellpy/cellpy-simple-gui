# The cold-context agent test

Protocol and results for the empirical check #127 asks for: *give an agent a cold
context, the docs, and a task, and see whether it succeeds without reading cellpy
source.* Run 2026-08-17 against the docs as they stood at that moment.

Kept here because it is repeatable, and because the result was more interesting
than a pass.

## Protocol

**Task** — the issue's own example: *"plot dQ/dV across these cells as a density
film"*, for cycles 1, 5 and 10, across the two bundled example cells.

Chosen because it is the [`layout=` vs `kind=`](../../docs/guides/03-plotting.md)
trap. Get it wrong and you get `scattergl` line curves that look entirely
reasonable, so the outcome is *measurable*: `histogram2d` or not.

**Two agents, because "an agent with docs succeeded" means nothing alone:**

| | Sees | May read cellpy source |
|---|---|---|
| **A** | an isolated directory containing only `llms.txt`, `llms-full.txt`, the guides, the API reference, the skill and the starter app | no |
| **B** (control) | nothing | yes — this is what someone does today |

Isolation is physical, not instructed: A's working directory is a copy of the
docs, so it cannot reach `src/` (which contains the answer) even by accident.

**Deliverable** — a runnable PEP 723 script plus `result.json`. The success
criterion is the trace type, and it was checked by re-running the script, not by
believing the report.

## Results

**Both succeeded. Both produced `{'histogram2d'}`.**

| | Route | Cost |
|---|---|---|
| A (docs) | read `llms.txt` → guide 3 → guides 1–2 → api-reference → starter → skill; wrote the call from the guide's snippet | 17 tool calls, ~8 min, **no experimentation** — correct on the first run |
| B (control) | grepped for `film`, read `collect/__init__.py`, `Collection.plot`, `resolve_collected_layout_kind`, then `sequence_plotter` to confirm the trace type | 24 tool calls, ~6 min, 4 source files, 2 REPL probes |

**So the docs do not make this possible; they make it cheap.** That is the honest
framing, and it is worth keeping — a documentation test that only ever proves
"the task can be done" is not measuring documentation.

The gap that matters is not the tool count. B had to read the *implementation* to
be sure `kind="film"` was the modern spelling rather than `method="film"`, and to
confirm the renderer produced a density heatmap. A took both on trust from one
snippet and was right. On a task where the source is less legible, or where the
agent stops reading earlier, that gap widens.

## What the test found

More than the pass/fail. Three of these are things the docs got *wrong*.

**1. The guides described a fixed bug as open.** A's environment resolved cellpy
**2.1.3**; this repo is pinned to 2.1.2. In 2.1.3, `layout="film"` is an accepted
alias and unknown layouts raise with the fix in the message — cellpy#874 is
closed. Guide 3 still presented the trap as current. Verified independently in a
clean 2.1.3 env before believing it.

**2. And the stale claim was in the one block type CI does not run.** A's sharpest
observation: the guides promise every Python block is executed, but that claim
lived in a ` ```pycon ` block — transcripts of things going *wrong*, deliberately
not executed. Which makes the "this is broken upstream" claims exactly the ones
with no check behind them. Fixed by asserting the *behaviour* separately
(`test_the_upstream_bugs_the_guides_describe_are_still_bugs`), version-aware, so
an upstream fix now fails CI instead of quietly making the prose wrong.

**3. A finding that turned out not to be a bug — and nearly got filed as one.**
A said the dQ/dV film was dropping data: 2328 rows collected, 891 plotted,
exactly the charge rows. The point count was right and the diagnosis was wrong.
Both renderers honour `direction`; it simply defaults to `charge`, and it is an
argument to `plot()` rather than a field on `IcaOptions` — so reading the options
dataclass suggests there is no control. We repeated the mistake, wrote it up as
"the film silently drops the discharge half-cycle", and only caught it by running
the discriminating case (`direction="both"` → 2328 for the film *and* the lines)
while preparing the upstream issue.

The lesson is about the shape of the evidence: a measurement that matches your
hypothesis is not a test of it. 891-of-2328 is equally consistent with "the film
drops data" and "the default is charge", and only the second call separates them.
Recorded as §35 with the correction kept visible.

**4. The control found two real gaps too:** a legacy `method="film"` spelling that
still works and that `ica_plotter`'s own docstring advertises, and `histscale`
for the film's colour scaling. Both now documented.

**5. The control was also wrong twice**, and would have degraded the docs if
taken at face value: it claimed `Collection.plot` silently swallows unrouted
kwargs (it raises `TypeError` from plotly express) and that `cycles` must be
passed at both the collect and plot layers for the film's y-range (identical
`(1, 10)` either way). Both checked, both false. **A subagent report is evidence,
not a result.**

**6. One criticism was the harness, not the docs.** A reported dead links to
`CELLPY_PAINPOINTS.md` and `README.md`. Those exist; they were not copied into the
isolated directory. Worth noting because it is the sort of finding that reads as
a docs defect and is not — and because the file it could not reach is precisely
the one that would have told it #874 was fixed.

## If you run it again

- Re-copy the doc subset; do not point the agent at the repo, or the isolation is
  gone and `src/core/collect.py` hands over the answer.
- **Pin the agent's cellpy** if you want to test the docs rather than discover a
  release. The version drift here was a lucky accident, but an uncontrolled one.
- Keep the control. It is what converts "it worked" into a measurement.
- Ask for the failure report explicitly ("be blunt; this judges the docs, not
  you"). Both useful findings came from that section, not from the task.
- Verify every claim in both reports before acting on it. Three of eleven were
  wrong — including one we believed, wrote into the guides, and were a few
  minutes from filing upstream.
- Before filing anything upstream, **re-run the repro on the latest release**.
  §34 still reproduced on 2.1.3 and was filed
  ([cellpy#939](https://github.com/jepegit/cellpy/issues/939)); §35 dissolved
  under the same check.
