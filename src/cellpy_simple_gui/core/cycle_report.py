"""Say which requested cycles a cell could not deliver (#175).

A cell explorer request names cycles; a cell either lacks a cycle outright or
has it but yields no curve rows for it (a truncated / corrupted cycle). Both
used to vanish silently — the curve was just not there, and when *no* cycle
survived the figure was blank. This module is pure bookkeeping: it compares
what was asked for with what the cell has and what the collected frame holds,
and words the result for the UI.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass


def compress_ranges(numbers: Iterable[int]) -> str:
    """``[22, 23, 24, 30]`` → ``"22–24, 30"`` (sorted, de-duplicated)."""
    nums = sorted(set(int(n) for n in numbers))
    if not nums:
        return ""
    parts: list[str] = []
    start = prev = nums[0]
    for n in nums[1:] + [None]:  # sentinel flushes the last run
        if n is not None and n == prev + 1:
            prev = n
            continue
        parts.append(str(start) if start == prev else f"{start}–{prev}")
        if n is not None:
            start = prev = n
    return ", ".join(parts)


def _plural(word: str, count: int) -> str:
    return word if count == 1 else word + "s"


@dataclass(frozen=True)
class CycleReport:
    """What one cell could not deliver for a request."""

    cell: str
    #: Requested but not among the cell's cycle numbers.
    missing: tuple[int, ...] = ()
    #: Among the cell's cycle numbers, yet produced no rows when collected.
    unreadable: tuple[int, ...] = ()
    #: ``(first, last)`` cycle the cell does have, for the "has 1–21" hint.
    available: tuple[int, int] | None = None

    def __bool__(self) -> bool:
        return bool(self.missing or self.unreadable)

    @property
    def dropped(self) -> tuple[int, ...]:
        return tuple(sorted(set(self.missing) | set(self.unreadable)))

    def message(self) -> str:
        clauses: list[str] = []
        if self.missing:
            clause = f"{_plural('cycle', len(self.missing))} {compress_ranges(self.missing)} not in data"
            if self.available:
                lo, hi = self.available
                clause += f" (has {lo})" if lo == hi else f" (has {lo}–{hi})"
            clauses.append(clause)
        if self.unreadable:
            clauses.append(
                f"{_plural('cycle', len(self.unreadable))} {compress_ranges(self.unreadable)} "
                "could not be read"
            )
        return f"{self.cell}: " + "; ".join(clauses)


def build_reports(
    requested: Mapping[str, Iterable[int]],
    available: Mapping[str, Iterable[int]],
    present: Iterable[tuple[str, int]] | None = None,
) -> list[CycleReport]:
    """One report per cell that lost at least one requested cycle.

    ``requested`` maps a cell label to the cycles asked for, ``available`` to
    the cycles the cell actually has (``cellpy_adapter.cycle_numbers``), and
    ``present`` lists the ``(label, cycle)`` pairs that made it into the
    collected frame. Pass ``present=None`` when nothing was collected, so no
    existing cycle is judged unreadable on the strength of an empty frame.
    Cells with nothing to report are left out; order follows ``requested``.
    """
    present_set = set(present) if present is not None else None
    reports: list[CycleReport] = []
    for label, cycles in requested.items():
        wanted = sorted(set(int(c) for c in cycles))
        has = set(int(c) for c in available.get(label, ()))
        missing = tuple(c for c in wanted if c not in has)
        unreadable: tuple[int, ...] = ()
        if present_set is not None:
            unreadable = tuple(
                c for c in wanted if c in has and (label, c) not in present_set
            )
        if not missing and not unreadable:
            continue
        span = (min(has), max(has)) if has else None
        reports.append(
            CycleReport(cell=label, missing=missing, unreadable=unreadable, available=span)
        )
    return reports


def messages(reports: Iterable[CycleReport]) -> list[str]:
    return [r.message() for r in reports if r]
