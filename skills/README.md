# Skills

Agent skills produced by this project. Copy one into your agent's skills
directory; they have no dependency on this repository once installed.

## `cellpy-app`

Writing Python that uses cellpy — the API surface, and the traps that produce
plausible-but-wrong output rather than an error.

```bash
# Claude Code, for one project
cp -r skills/cellpy-app .claude/skills/

# Claude Code, for everything you do
cp -r skills/cellpy-app ~/.claude/skills/
```

It carries its own copy of [`docs/api-reference.md`](../docs/api-reference.md)
under `reference/`, so it works offline and away from this repo. Both copies are
written by [`tools/gen_api_reference.py`](../tools/gen_api_reference.py) in the
same run and checked by `tests/test_api_reference.py`, so they cannot drift apart
or fall behind the installed cellpy.

**Regenerate after upgrading cellpy:**

```bash
uv run tools/gen_api_reference.py
```
