"""Structured reports produced by flowguard checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .core import FrozenMetadata, freeze_metadata
from .export import check_report_to_dict, check_report_to_json_text
from .trace import Trace


@dataclass(frozen=True)
class DeadBranch:
    """A workflow branch that could not make progress."""

    reason: str
    trace: Trace
    function_name: str = ""
    function_input: Any = None
    state: Any = None
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))


@dataclass(frozen=True)
class ExceptionBranch:
    """A workflow branch that raised while evaluating a block or invariant."""

    error_type: str
    message: str
    trace: Trace
    function_name: str = ""
    function_input: Any = None
    state: Any = None


@dataclass(frozen=True)
class InvariantViolation:
    """A failed invariant with its counterexample trace."""

    invariant_name: str
    description: str
    message: str
    state: Any
    trace: Trace
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))


@dataclass(frozen=True)
class ReachabilityFailure:
    """A required reachable condition was not found."""

    name: str
    description: str = ""
    message: str = ""


@dataclass(frozen=True)
class CheckReport:
    """Structured outcome of an exhaustive model check."""

    ok: bool
    violations: tuple[InvariantViolation, ...] = ()
    traces: tuple[Trace, ...] = ()
    summary: str = ""
    dead_branches: tuple[DeadBranch, ...] = ()
    exception_branches: tuple[ExceptionBranch, ...] = ()
    reachability_failures: tuple[ReachabilityFailure, ...] = ()
    explored_sequences: tuple[tuple[Any, ...], ...] = ()

    def format_text(self, max_examples: int = 3) -> str:
        lines = [
            f"status: {'OK' if self.ok else 'VIOLATION'}",
            self.summary or f"traces={len(self.traces)} sequences={len(self.explored_sequences)}",
            f"invariant_violations: {len(self.violations)}",
            f"dead_branches: {len(self.dead_branches)}",
            f"exceptions: {len(self.exception_branches)}",
            f"reachability_failures: {len(self.reachability_failures)}",
        ]

        for failure in self.reachability_failures[:max_examples]:
            lines.extend(
                [
                    "",
                    f"reachability: {failure.name}",
                    f"message: {failure.message or failure.description}",
                ]
            )

        for violation in self.violations[:max_examples]:
            lines.extend(
                [
                    "",
                    f"invariant: {violation.invariant_name}",
                    f"message: {violation.message}",
                    "counterexample:",
                    violation.trace.format_text(),
                ]
            )

        for dead in self.dead_branches[:max_examples]:
            lines.extend(
                [
                    "",
                    f"dead_branch: {dead.function_name or '(workflow)'}",
                    f"reason: {dead.reason}",
                    dead.trace.format_text(),
                ]
            )

        for exc in self.exception_branches[:max_examples]:
            lines.extend(
                [
                    "",
                    f"exception: {exc.error_type} in {exc.function_name or '(workflow)'}",
                    f"message: {exc.message}",
                    exc.trace.format_text(),
                ]
            )

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return check_report_to_dict(self)

    def to_json_text(self, indent: int = 2) -> str:
        return check_report_to_json_text(self, indent=indent)


__all__ = [
    "CheckReport",
    "DeadBranch",
    "ExceptionBranch",
    "InvariantViolation",
    "ReachabilityFailure",
]
