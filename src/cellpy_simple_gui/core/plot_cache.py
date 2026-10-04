"""In-process plot cache. Behaviour lives in the constants below.

Edit those when a field moves between restyle and ``collection.plot``, when
the memory cap is wrong, or when invalidation has to split. Plot functions
ask this module for a slot; they do not choose the rules themselves.

``CSG_PLOT_CACHE=0`` forces a miss and stores nothing. A caller can pass
``use_cache=False`` to opt out of one call without turning the process off.
"""

from __future__ import annotations

import dataclasses
import os
import threading
from collections import OrderedDict
from collections.abc import Callable
from typing import Any, TypeVar

# Applied only in ``_restyle``. A name absent from this set is structural:
# changing it rebuilds the collection and the figure.
COSMETIC: frozenset[str] = frozenset({"color_scheme", "group_shade", "shade_spread"})

# Library methods that bump ``revision``. A new writer calls ``_touch`` and
# is added here. ``mark_saved`` is provenance and stays out.
BUMPS: frozenset[str] = frozenset(
    {
        "add_cell",
        "restore_cell",
        "update",
        "remove",
        "clear",
        "set_selection",
        "set_group_label",
    }
)
QUIET: frozenset[str] = frozenset({"mark_saved"})

MAX_ENTRIES = 8

T = TypeVar("T")
_MISS = object()


def enabled() -> bool:
    """True unless ``CSG_PLOT_CACHE`` is ``0``."""
    return os.environ.get("CSG_PLOT_CACHE", "1").strip() != "0"


def freeze(value: Any) -> Any:
    """A hashable picture of ``value`` for a cache key.

    Dataclasses and pydantic models freeze by their fields. A callable freezes
    as its ``repr``, which is stable for one function object in this process.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return tuple(sorted((str(k), freeze(v)) for k, v in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(freeze(v) for v in value)
    if isinstance(value, (set, frozenset)):
        return tuple(sorted((freeze(v) for v in value), key=repr))
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        return freeze(dump())
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return freeze(dataclasses.asdict(value))
    if callable(value):
        return ("callable", repr(value))
    return ("repr", type(value).__name__, repr(value))


def record_token(records: list[Any]) -> tuple:
    """Identity of the records a collect call saw.

    ``cache_revision`` changes when the owning library is touched, so a mass
    edit misses even if the cell object is the same one. ``id(cell)`` keeps
    two libraries that both sit at revision 1 from sharing an entry.
    """
    return tuple(
        (
            r.id,
            r.cache_revision,
            id(r.cell),
            r.group,
            r.label,
            r.group_label,
            r.selected,
        )
        for r in records
    )


def structural(payload: dict[str, Any]) -> tuple:
    """Cache-key fragment with cosmetic fields removed."""
    return freeze({k: v for k, v in payload.items() if k not in COSMETIC})


class _Memo:
    """Small insertion-ordered memo. Not used across a library touch."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: OrderedDict[Any, Any] = OrderedDict()

    def get(self, key: Any) -> Any:
        if not enabled():
            return _MISS
        with self._lock:
            if key not in self._items:
                return _MISS
            self._items.move_to_end(key)
            return self._items[key]

    def put(self, key: Any, value: Any) -> None:
        if not enabled():
            return
        with self._lock:
            self._items[key] = value
            self._items.move_to_end(key)
            while len(self._items) > MAX_ENTRIES:
                self._items.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


_collect = _Memo()
_figures = _Memo()


def invalidate() -> None:
    """Drop both memos. ``Library._touch`` calls this."""
    _collect.clear()
    _figures.clear()


def cached_collect(
    name: str,
    records: list[Any],
    args: dict[str, Any],
    build: Callable[[], T],
    *,
    use_cache: bool = True,
) -> T:
    """Return a cached collection, or build one and store it.

    A hit is the same object that was stored. ``use_cache=False`` always
    builds and does not store.
    """
    if not use_cache or not enabled():
        return build()
    try:
        key = (name, record_token(records), freeze(args))
    except Exception:
        return build()
    hit = _collect.get(key)
    if hit is not _MISS:
        return hit
    value = build()
    _collect.put(key, value)
    return value


def clone_figure(fig: Any) -> Any:
    """A figure the caller can restyle without painting the stored one.

    ``copy.deepcopy`` shares Plotly buffers, so a later restyle paints the
    stored figure. A JSON round-trip does not.
    """
    import plotly.io as pio

    return pio.from_json(pio.to_json(fig))


def cached_figure(
    key_parts: dict[str, Any],
    build_base: Callable[[], tuple[Any, Any]],
    finish: Callable[[Any, Any], T],
    *,
    use_cache: bool = True,
) -> T:
    """Reuse a pre-restyle figure.

    ``build_base`` returns ``(figure, extra)`` taken before ``_restyle``.
    ``finish`` restyles a figure and returns the JSON. The stored figure is
    a clone, and a hit clones it again.
    """
    if not use_cache or not enabled():
        fig, extra = build_base()
        return finish(fig, extra)
    try:
        key = structural(key_parts)
    except Exception:
        fig, extra = build_base()
        return finish(fig, extra)
    hit = _figures.get(key)
    if hit is not _MISS:
        fig, extra = hit
        return finish(clone_figure(fig), extra)
    fig, extra = build_base()
    _figures.put(key, (clone_figure(fig), extra))
    return finish(fig, extra)
