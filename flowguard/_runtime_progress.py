"""Shared runtime progress controls for finite explorers."""

from __future__ import annotations

import os


def progress_disabled_by_environment() -> bool:
    value = os.environ.get("FLOWGUARD_PROGRESS")
    return value is not None and value.strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }


def progress_thresholds(
    total_work: int,
    progress_steps: int,
) -> tuple[tuple[int, int], ...]:
    if total_work < 1 or progress_steps < 1:
        return ()
    thresholds: dict[int, int] = {}
    for step in range(1, progress_steps + 1):
        threshold = max(
            1,
            (total_work * step + progress_steps - 1) // progress_steps,
        )
        percent = min(100, (step * 100) // progress_steps)
        thresholds[threshold] = percent
    return tuple(sorted(thresholds.items()))


__all__ = ["progress_disabled_by_environment", "progress_thresholds"]
