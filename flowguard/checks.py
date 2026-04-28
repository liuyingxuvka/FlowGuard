"""Convenience constructors for invariants and reachability checks."""

from __future__ import annotations

from collections import Counter
from typing import Any, Callable, Iterable

from .core import Invariant, InvariantResult
from .explorer import ReachabilityCondition


StatePredicate = Callable[[Any], bool]
StateTracePredicate = Callable[[Any, Any], bool]
Selector = Callable[[Any], Iterable[Any]]


def state_invariant(
    name: str,
    description: str,
    predicate: StateTracePredicate,
    message: str | Callable[[Any, Any], str] = "",
) -> Invariant:
    """Create an invariant from a `(state, trace) -> bool` predicate."""

    def check(state: Any, trace: Any) -> bool | InvariantResult:
        passed = bool(predicate(state, trace))
        if passed:
            return InvariantResult.pass_()
        rendered = message(state, trace) if callable(message) else message
        return InvariantResult.fail(rendered or f"invariant failed: {name}")

    return Invariant(name=name, description=description, predicate=check)


def no_duplicate_values(
    name: str,
    description: str,
    selector: Selector,
    value_name: str = "value",
) -> Invariant:
    """Require the selected values to contain no duplicates."""

    def check(state: Any, trace: Any) -> InvariantResult:
        del trace
        values = tuple(selector(state))
        counts = Counter(values)
        duplicates = tuple(value for value, count in counts.items() if count > 1)
        if not duplicates:
            return InvariantResult.pass_()
        return InvariantResult.fail(
            f"duplicate {value_name}s: {duplicates!r}",
            {"duplicates": duplicates},
        )

    return Invariant(name=name, description=description, predicate=check)


def require_label(label: str, description: str = "") -> ReachabilityCondition:
    """Require at least one explored trace to include a label."""

    return ReachabilityCondition(
        name=f"label:{label}",
        description=description or f"label {label!r} must be reachable",
        predicate=lambda state, trace: trace.has_label(label),
    )


def require_reachable(
    name: str,
    predicate: StateTracePredicate,
    description: str = "",
) -> ReachabilityCondition:
    """Require at least one explored path to match a predicate."""

    return ReachabilityCondition(name=name, predicate=predicate, description=description)


__all__ = [
    "ReachabilityCondition",
    "no_duplicate_values",
    "require_label",
    "require_reachable",
    "state_invariant",
]
