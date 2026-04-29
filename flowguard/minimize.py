"""Deterministic counterexample sequence minimization helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

from .export import to_jsonable


RunSequence = Callable[[tuple[Any, ...]], Any]
FailurePredicate = Callable[[Any], bool]


@dataclass(frozen=True)
class ReductionStep:
    """One successful deterministic sequence reduction."""

    pass_index: int
    removed_start: int
    removed_length: int
    candidate_length: int
    sequence: tuple[Any, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "pass_index", int(self.pass_index))
        object.__setattr__(self, "removed_start", int(self.removed_start))
        object.__setattr__(self, "removed_length", int(self.removed_length))
        object.__setattr__(self, "candidate_length", int(self.candidate_length))
        object.__setattr__(self, "sequence", tuple(self.sequence))

    def to_dict(self) -> dict[str, Any]:
        return {
            "pass_index": self.pass_index,
            "removed_start": self.removed_start,
            "removed_length": self.removed_length,
            "candidate_length": self.candidate_length,
            "sequence": to_jsonable(self.sequence),
        }


@dataclass(frozen=True)
class MinimizedCounterexample:
    """Original and minimized failing external input sequences."""

    original_sequence: tuple[Any, ...]
    minimized_sequence: tuple[Any, ...]
    status: str
    reason: str = ""
    attempts: int = 0
    passes: int = 0
    reduction_steps: tuple[ReductionStep, ...] = ()
    violation_name: str | None = None
    original_result: Any = field(default=None, compare=False)
    minimized_result: Any = field(default=None, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "original_sequence", tuple(self.original_sequence))
        object.__setattr__(self, "minimized_sequence", tuple(self.minimized_sequence))
        object.__setattr__(self, "status", str(self.status))
        object.__setattr__(self, "reason", str(self.reason or ""))
        object.__setattr__(self, "attempts", int(self.attempts))
        object.__setattr__(self, "passes", int(self.passes))
        object.__setattr__(self, "reduction_steps", tuple(self.reduction_steps))

    @property
    def reduction_found(self) -> bool:
        return self.minimized_sequence != self.original_sequence

    def format_text(self) -> str:
        lines = [
            "=== flowguard counterexample minimization ===",
            f"status: {self.status}",
            f"original_length: {len(self.original_sequence)}",
            f"minimized_length: {len(self.minimized_sequence)}",
            f"attempts: {self.attempts}",
            f"passes: {self.passes}",
        ]
        if self.violation_name:
            lines.append(f"violation_name: {self.violation_name}")
        if self.reason:
            lines.append(f"reason: {self.reason}")
        lines.extend(
            [
                f"original_sequence: {self.original_sequence!r}",
                f"minimized_sequence: {self.minimized_sequence!r}",
            ]
        )
        if self.reduction_steps:
            lines.append("reductions:")
            for step in self.reduction_steps:
                lines.append(
                    "  - "
                    f"pass={step.pass_index} start={step.removed_start} "
                    f"length={step.removed_length} candidate_length={step.candidate_length}"
                )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_sequence": to_jsonable(self.original_sequence),
            "minimized_sequence": to_jsonable(self.minimized_sequence),
            "original_length": len(self.original_sequence),
            "minimized_length": len(self.minimized_sequence),
            "status": self.status,
            "reason": self.reason,
            "attempts": self.attempts,
            "passes": self.passes,
            "reduction_found": self.reduction_found,
            "violation_name": self.violation_name,
            "reduction_steps": [step.to_dict() for step in self.reduction_steps],
            "original_result": to_jsonable(self.original_result),
            "minimized_result": to_jsonable(self.minimized_result),
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


def minimize_failing_sequence(
    *,
    external_input_sequence: Sequence[Any],
    run_sequence: RunSequence,
    failure_predicate: FailurePredicate,
    max_passes: int = 8,
) -> MinimizedCounterexample:
    """Shrink a failing sequence by deterministic contiguous deletion.

    The minimizer only deletes inputs. It does not mutate values, sample
    randomly, or claim optimality. The returned report always retains the
    original sequence alongside the best sequence found.
    """

    original = tuple(external_input_sequence)
    attempts = 1
    original_result = run_sequence(original)
    if not failure_predicate(original_result):
        return MinimizedCounterexample(
            original_sequence=original,
            minimized_sequence=original,
            status="original_does_not_fail",
            reason="failure_predicate returned false for the original sequence",
            attempts=attempts,
            passes=0,
            original_result=original_result,
            minimized_result=original_result,
        )

    current = original
    current_result = original_result
    reductions: list[ReductionStep] = []
    passes_run = 0
    max_passes = max(1, int(max_passes))

    while passes_run < max_passes:
        passes_run += 1
        changed = False
        for chunk_size in range(len(current), 0, -1):
            for start in range(0, len(current) - chunk_size + 1):
                candidate = current[:start] + current[start + chunk_size:]
                attempts += 1
                result = run_sequence(candidate)
                if not failure_predicate(result):
                    continue
                current = candidate
                current_result = result
                reductions.append(
                    ReductionStep(
                        pass_index=passes_run,
                        removed_start=start,
                        removed_length=chunk_size,
                        candidate_length=len(candidate),
                        sequence=candidate,
                    )
                )
                changed = True
                break
            if changed:
                break
        if not changed:
            break

    if current == original:
        status = "no_reduction_found"
        reason = "no contiguous deletion preserved the same failure"
    else:
        status = "reduced"
        reason = "removed contiguous input chunks while preserving the failure"
        if passes_run >= max_passes and reductions and reductions[-1].pass_index == passes_run:
            reason = "max_passes reached after a successful reduction"

    return MinimizedCounterexample(
        original_sequence=original,
        minimized_sequence=current,
        status=status,
        reason=reason,
        attempts=attempts,
        passes=passes_run,
        reduction_steps=tuple(reductions),
        original_result=original_result,
        minimized_result=current_result,
    )


def _report_has_violation(report: Any, violation_name: str | None) -> bool:
    if violation_name is None:
        return not bool(getattr(report, "ok", True))

    for violation in getattr(report, "violations", ()):
        if getattr(violation, "invariant_name", None) == violation_name:
            return True
    for failure in getattr(report, "reachability_failures", ()):
        if getattr(failure, "name", None) == violation_name:
            return True
    for dead_branch in getattr(report, "dead_branches", ()):
        if getattr(dead_branch, "function_name", None) == violation_name:
            return True
    for exception_branch in getattr(report, "exception_branches", ()):
        if getattr(exception_branch, "function_name", None) == violation_name:
            return True
    return False


def minimize_report_counterexample(
    explorer_factory: Callable[[tuple[Any, ...]], Any],
    failing_sequence: Sequence[Any],
    violation_name: str | None = None,
    max_passes: int = 8,
) -> MinimizedCounterexample:
    """Minimize a failing sequence for a factory that returns a report or Explorer.

    `explorer_factory(sequence)` should run exactly the supplied sequence, or
    return an object with an `explore()` method that does so. `violation_name`
    keeps the minimizer focused on the same invariant or reachability failure.
    """

    def run_sequence(sequence: tuple[Any, ...]) -> Any:
        result = explorer_factory(tuple(sequence))
        explore = getattr(result, "explore", None)
        if callable(explore):
            return explore()
        return result

    minimized = minimize_failing_sequence(
        external_input_sequence=tuple(failing_sequence),
        run_sequence=run_sequence,
        failure_predicate=lambda report: _report_has_violation(report, violation_name),
        max_passes=max_passes,
    )
    return MinimizedCounterexample(
        original_sequence=minimized.original_sequence,
        minimized_sequence=minimized.minimized_sequence,
        status=minimized.status,
        reason=minimized.reason,
        attempts=minimized.attempts,
        passes=minimized.passes,
        reduction_steps=minimized.reduction_steps,
        violation_name=violation_name,
        original_result=minimized.original_result,
        minimized_result=minimized.minimized_result,
    )


__all__ = [
    "FailurePredicate",
    "MinimizedCounterexample",
    "ReductionStep",
    "RunSequence",
    "minimize_failing_sequence",
    "minimize_report_counterexample",
]
