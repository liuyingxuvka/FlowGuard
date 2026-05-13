"""Deterministic exhaustive exploration for flowguard workflows."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from itertools import product
from typing import Any, Callable, Iterable, Sequence

from .core import InvariantResult
from .report import (
    CheckReport,
    DeadBranch,
    ExceptionBranch,
    InvariantViolation,
    ReachabilityFailure,
)
from .trace import Trace
from .workflow import TerminalPredicate, Workflow, WorkflowPath


ReachabilityPredicate = Callable[[Any, Trace], bool]


@dataclass(frozen=True)
class ReachabilityCondition:
    """A condition that must be reached by at least one explored path."""

    name: str
    predicate: ReachabilityPredicate
    description: str = ""

    def matches(self, state: Any, trace: Trace) -> bool:
        return bool(self.predicate(state, trace))


def enumerate_input_sequences(
    external_inputs: Sequence[Any],
    max_sequence_length: int,
) -> tuple[tuple[Any, ...], ...]:
    """Enumerate all non-empty input sequences up to a finite length."""

    if max_sequence_length < 1:
        raise ValueError("max_sequence_length must be at least 1")
    inputs = tuple(external_inputs)
    return tuple(
        sequence
        for length in range(1, max_sequence_length + 1)
        for sequence in product(inputs, repeat=length)
    )


def _invariant_name(invariant: Any) -> str:
    return str(getattr(invariant, "name", getattr(invariant, "__name__", type(invariant).__name__)))


def _invariant_description(invariant: Any) -> str:
    return str(getattr(invariant, "description", ""))


def _check_invariant(invariant: Any, state: Any, trace: Trace) -> InvariantResult:
    check = getattr(invariant, "check", None)
    try:
        if check is not None:
            result = check(state, trace)
        else:
            result = invariant(state, trace)
    except Exception as exc:
        return InvariantResult.fail(
            f"invariant raised {type(exc).__name__}: {exc}",
            {"invariant": _invariant_name(invariant)},
        )
    if isinstance(result, InvariantResult):
        return result
    passed = bool(result)
    if passed:
        return InvariantResult.pass_()
    return InvariantResult.fail(f"invariant failed: {_invariant_name(invariant)}")


def _progress_disabled_by_environment() -> bool:
    value = os.environ.get("FLOWGUARD_PROGRESS")
    return value is not None and value.strip().lower() in {"0", "false", "no", "off"}


def _progress_thresholds(total_work: int, progress_steps: int) -> tuple[tuple[int, int], ...]:
    if total_work < 1 or progress_steps < 1:
        return ()
    thresholds: dict[int, int] = {}
    for step in range(1, progress_steps + 1):
        threshold = max(1, (total_work * step + progress_steps - 1) // progress_steps)
        percent = min(100, (step * 100) // progress_steps)
        thresholds[threshold] = percent
    return tuple(sorted(thresholds.items()))


@dataclass(frozen=True)
class Explorer:
    """Exhaustively explore finite external input sequences."""

    workflow: Workflow
    initial_states: tuple[Any, ...]
    external_inputs: tuple[Any, ...]
    invariants: tuple[Any, ...] = ()
    max_sequence_length: int = 1
    terminal_predicate: TerminalPredicate | None = None
    success_predicate: ReachabilityPredicate | None = None
    required_labels: tuple[str, ...] = ()
    required_reachable: tuple[ReachabilityCondition, ...] = ()
    assumption_card: Any = None
    progress_steps: int = 10

    def __init__(
        self,
        workflow: Workflow,
        initial_states: Iterable[Any],
        external_inputs: Sequence[Any],
        invariants: Sequence[Any] = (),
        max_sequence_length: int = 1,
        terminal_predicate: TerminalPredicate | None = None,
        success_predicate: ReachabilityPredicate | None = None,
        required_labels: Sequence[str] = (),
        required_reachable: Sequence[ReachabilityCondition] = (),
        assumption_card: Any = None,
        progress_steps: int = 10,
    ) -> None:
        object.__setattr__(self, "workflow", workflow)
        object.__setattr__(self, "initial_states", tuple(initial_states))
        object.__setattr__(self, "external_inputs", tuple(external_inputs))
        object.__setattr__(self, "invariants", tuple(invariants))
        object.__setattr__(self, "max_sequence_length", max_sequence_length)
        object.__setattr__(self, "terminal_predicate", terminal_predicate)
        object.__setattr__(self, "success_predicate", success_predicate)
        object.__setattr__(self, "required_labels", tuple(required_labels))
        object.__setattr__(self, "required_reachable", tuple(required_reachable))
        object.__setattr__(self, "assumption_card", assumption_card)
        object.__setattr__(self, "progress_steps", int(progress_steps))

    def explore(self) -> CheckReport:
        sequences = enumerate_input_sequences(self.external_inputs, self.max_sequence_length)
        violations: list[InvariantViolation] = []
        dead_branches: list[DeadBranch] = []
        exception_branches: list[ExceptionBranch] = []
        observed_paths: list[WorkflowPath] = []
        total_work = len(self.initial_states) * len(sequences)
        progress_enabled = self.progress_steps > 0 and not _progress_disabled_by_environment()
        progress_thresholds = _progress_thresholds(total_work, self.progress_steps)
        next_threshold_index = 0
        completed_work = 0

        if progress_enabled and total_work:
            print(
                f"[flowguard] start phase=explore work_total={total_work} "
                f"progress_steps={self.progress_steps}",
                file=sys.stderr,
                flush=True,
            )

        for initial_state in self.initial_states:
            for sequence in sequences:
                active = (
                    WorkflowPath(
                        current_input=None,
                        state=initial_state,
                        trace=Trace(initial_state=initial_state, external_inputs=sequence),
                    ),
                )

                for external_input in sequence:
                    next_active: list[WorkflowPath] = []
                    for path in active:
                        run = self.workflow.execute(
                            initial_state=path.state,
                            external_input=external_input,
                            trace=path.trace.with_external_inputs(sequence),
                            terminal_predicate=self.terminal_predicate,
                        )
                        dead_branches.extend(run.dead_branches)
                        exception_branches.extend(run.exception_branches)
                        for completed_path in run.completed_paths:
                            observed_paths.append(completed_path)
                            violations.extend(self._check_path_invariants(completed_path))
                        next_active.extend(run.completed_paths)
                    active = tuple(next_active)
                    if not active:
                        break
                completed_work += 1
                if progress_enabled:
                    while (
                        next_threshold_index < len(progress_thresholds)
                        and completed_work >= progress_thresholds[next_threshold_index][0]
                    ):
                        _, percent = progress_thresholds[next_threshold_index]
                        print(
                            f"[flowguard] progress {percent}% work={completed_work}/{total_work} "
                            f"traces={len(observed_paths)} violations={len(violations)}",
                            file=sys.stderr,
                            flush=True,
                        )
                        next_threshold_index += 1

        traces = tuple(path.trace for path in observed_paths)
        reachability_failures = self._check_reachability(observed_paths)
        ok = not violations and not dead_branches and not exception_branches and not reachability_failures
        summary = (
            f"sequences={len(sequences)} initial_states={len(self.initial_states)} "
            f"traces={len(traces)}"
        )
        return CheckReport(
            ok=ok,
            violations=tuple(violations),
            traces=traces,
            summary=summary,
            dead_branches=tuple(dead_branches),
            exception_branches=tuple(exception_branches),
            reachability_failures=tuple(reachability_failures),
            explored_sequences=sequences,
            assumption_card=self.assumption_card,
        )

    def _check_path_invariants(self, path: WorkflowPath) -> list[InvariantViolation]:
        violations: list[InvariantViolation] = []
        for invariant in self.invariants:
            result = _check_invariant(invariant, path.state, path.trace)
            if result.ok:
                continue
            violations.append(
                InvariantViolation(
                    invariant_name=_invariant_name(invariant),
                    description=_invariant_description(invariant),
                    message=result.message,
                    state=path.state,
                    trace=path.trace,
                    metadata=result.metadata,
                )
            )
        return violations

    def _check_reachability(self, paths: Sequence[WorkflowPath]) -> list[ReachabilityFailure]:
        failures: list[ReachabilityFailure] = []

        for label in self.required_labels:
            if not any(path.trace.has_label(label) for path in paths):
                failures.append(
                    ReachabilityFailure(
                        name=f"label:{label}",
                        description=f"label {label!r} must be reachable",
                        message=f"no explored trace reached label {label!r}",
                    )
                )

        if self.success_predicate is not None:
            matched = False
            for path in paths:
                try:
                    matched = bool(self.success_predicate(path.state, path.trace))
                except Exception as exc:
                    failures.append(
                        ReachabilityFailure(
                            name="success_predicate",
                            description="success predicate raised",
                            message=f"{type(exc).__name__}: {exc}",
                        )
                    )
                    matched = True
                    break
                if matched:
                    break
            if not matched:
                failures.append(
                    ReachabilityFailure(
                        name="success_predicate",
                        description="at least one success predicate match is required",
                        message="no explored trace matched the success predicate",
                    )
                )

        for condition in self.required_reachable:
            matched = False
            for path in paths:
                try:
                    matched = condition.matches(path.state, path.trace)
                except Exception as exc:
                    failures.append(
                        ReachabilityFailure(
                            name=condition.name,
                            description=condition.description,
                            message=f"reachability predicate raised {type(exc).__name__}: {exc}",
                        )
                    )
                    matched = True
                    break
                if matched:
                    break
            if not matched:
                failures.append(
                    ReachabilityFailure(
                        name=condition.name,
                        description=condition.description,
                        message=f"required reachable condition was not found: {condition.name}",
                    )
                )

        return failures


__all__ = ["Explorer", "ReachabilityCondition", "enumerate_input_sequences"]
