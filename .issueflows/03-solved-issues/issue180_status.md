# Status — #180 make smarter caching

- [x] Done

## What's done

- Plan accepted. Cache rules live in `core/plot_cache.py`.
- `Library.revision` bumps on data and view edits. `mark_saved` does not.
- Collect memo plus a pre-restyle figure memo. Colour, group shade, and shade spread restyle a stored figure.
- Browser memo keyed by revision and the full request body.
- Design note: `.issueflows/04-designs-and-guides/plot-cache.md`.
- `uv run --extra dev pytest tests/test_plot_cache.py tests/test_core.py tests/test_api.py` passed (2 skips).
- No `HISTORY.md` at the repo root, so the changelog step was skipped.
- No version bump.

## Remaining work

- None.
