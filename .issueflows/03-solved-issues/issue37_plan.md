# Plan — Issue #37

## Goal

Make safe/muted spread bands translucent (rgba fill) without washing out mean lines.

## Approach

1. In `_apply_colorway`, convert series hex to `rgba(..., alpha≈0.28)` for filled traces instead of solid hex + `tr.opacity`.
2. Keep line/marker colors fully opaque hex.
3. Leave `cellpy` path unchanged (`COLOR_SCHEMES["cellpy"] is None`).
4. Add structural test: group-avg + spread + safe/muted → fillcolor has alpha.

## Files to touch

- `src/cellpy_simple_gui/core/collect.py`
- `tests/test_core.py`
- optionally `.issueflows/04-designs-and-guides/plot-appearance.md` (one line)

## Test strategy

- New unit test asserting rgba/alpha on filled traces for safe and muted.
- Full `uv run pytest`.
