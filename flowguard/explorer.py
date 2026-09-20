"""Deterministic exhaustive exploration for flowguard workflows."""

from __future__ import annotations

import sys
import os
import time
from dataclasses import dataclass, field
from itertools import product
from typing import Any, Callable, Iterable, Sequence

from ._runtime_progress import (
    progress_disabled_by_environment as _progress_disabled_by_environment,
    progress_thresholds as _progress_thresholds,
)
from .core import InvariantResult
from .report import (
    CheckReport,
    DeadBranch,
    ExceptionBranch,
    EXPLORATION_STATUS_BUDGET_EXHAUSTED,
    EXPLORATION_STATUS_COMPLETE,
    EXPLORATION_STATUS_STOPPED_ON_COUNTEREXAMPLE,
    InvariantViolation,
    ReachabilityFailure,
)
from .trace import Trace
from .workflow import TerminalPredicate, Workflow, WorkflowPath


# A terminal owner needs to retain a bounded witness set, not one copy of the
# same failure for every finite input sequence. The normal interactive
# explorer remains lossless; this cap is used only when
# FLOWGUARD_COMPACT_TRACE_STORAGE=1 is explicitly selected by a bounded runner.
_COMPACT_FINDING_LIMIT = 256


ReachabilityPredicate = Callable[[Any, Trace], bool]


@dataclass(frozen=True)
class ReachabilityCondition:
    """A condition that must be reached by at least one explored path."""

    name: str
    predicate: ReachabilityPredicate
    description: str = ""

    def matches(self, state: Any, trace: Trace) -> bool:
        return bool(self.predicate(state, trace))


@dataclass
class _ReachabilityState:
    """Truth state accumulated independently from retained witness paths."""

    required_label_matches: list[bool]
    success_matched: bool = False
    success_error: str = ""
    required_matches: list[bool] = field(default_factory=list)
    required_errors: list[str] = field(default_factory=list)


def enumerate_input_sequences(
    external_inputs: Sequence[Any],
    max_sequence_length: int,
) -> tuple[tuple[Any, ...], ...]:
    """Enumerate all non-empty input sequences up to a finite length."""

    if max_sequence_length < 1:
        raise ValueError("max_sequence_length must be at least 1")
    inputs = tuple(external_inputs)
    return tuple(_iter_input_sequences(inputs, max_sequence_length))


def _iter_input_sequences(
    external_inputs: Sequence[Any],
    max_sequence_length: int,
) -> Iterable[tuple[Any, ...]]:
    """Yield finite sequences without materializing the whole domain."""

    if max_sequence_length < 1:
        raise ValueError("max_sequence_length must be at least 1")
    inputs = tuple(external_inputs)
    for length in range(1, max_sequence_length + 1):
        yield from product(inputs, repeat=length)


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
    max_failures: int | None = None
    failure_witness_limit: int | None = None
    max_transitions: int | None = None
    deadline: float | None = None

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
        max_failures: int | None = None,
        failure_witness_limit: int | None = None,
        max_transitions: int | None = None,
        deadline: float | None = None,
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
        if max_failures is not None and int(max_failures) < 1:
            raise ValueError("max_failures must be at least 1 when provided")
        if failure_witness_limit is not None and int(failure_witness_limit) < 1:
            raise ValueError("failure_witness_limit must be at least 1 when provided")
        if max_transitions is not None and int(max_transitions) < 1:
            raise ValueError("max_transitions must be at least 1 when provided")
        object.__setattr__(self, "max_failures", None if max_failures is None else int(max_failures))
        object.__setattr__(
            self,
            "failure_witness_limit",
            None if failure_witness_limit is None else int(failure_witness_limit),
        )
        object.__setattr__(self, "max_transitions", None if max_transitions is None else int(max_transitions))
        object.__setattr__(self, "deadline", deadline)

    def explore(self) -> CheckReport:
        if self.max_sequence_length < 1:
            raise ValueError("max_sequence_length must be at least 1")
        compact_trace_storage = os.environ.get("FLOWGUARD_COMPACT_TRACE_STORAGE") == "1"
        # Keep both public enumeration semantics and ordinary exploration
        # finite, but do not materialize the Cartesian domain before the first
        # transition.  A bounded caller can therefore stop on its first
        # counterexample or deadline without paying for the unexplored suffix.
        input_count = len(self.external_inputs)
        sequence_count = sum(
            input_count**length for length in range(1, self.max_sequence_length + 1)
        )

        def sequence_factory() -> Iterable[tuple[Any, ...]]:
            """Return a fresh finite sequence iterator for one initial state."""

            return _iter_input_sequences(self.external_inputs, self.max_sequence_length)
        violations: list[InvariantViolation] = []
        dead_branches: list[DeadBranch] = []
        exception_branches: list[ExceptionBranch] = []
        observed_paths: list[WorkflowPath] = []
        observed_sequences: list[tuple[Any, ...]] = []
        observed_trace_count = 0
        observed_failure_count = 0
        sequence_started_count = 0
        transition_count = 0
        exploration_complete = True
        termination_reason = "completed"
        exploration_status = EXPLORATION_STATUS_COMPLETE
        reachability_state = _ReachabilityState(
            required_label_matches=[False] * len(self.required_labels),
            required_matches=[False] * len(self.required_reachable),
            required_errors=[""] * len(self.required_reachable),
        )
        total_work = len(self.initial_states) * sequence_count
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
            if not exploration_complete:
                break
            # A compact run must not share one exhausted generator across
            # initial states: every finite initial-state/sequence pair is an
            # independent exploration obligation.
            for sequence in sequence_factory():
                if self.deadline is not None and time.monotonic() >= self.deadline:
                    exploration_complete = False
                    termination_reason = "deadline_exhausted"
                    exploration_status = EXPLORATION_STATUS_BUDGET_EXHAUSTED
                    break
                if self.max_transitions is not None and transition_count >= self.max_transitions:
                    exploration_complete = False
                    termination_reason = "max_transitions_exhausted"
                    exploration_status = EXPLORATION_STATUS_BUDGET_EXHAUSTED
                    break
                sequence_started_count += 1
                if not compact_trace_storage:
                    observed_sequences.append(sequence)
                active = (
                    WorkflowPath(
                        current_input=None,
                        state=initial_state,
                        trace=Trace(initial_state=initial_state, external_inputs=sequence),
                    ),
                )

                for external_input in sequence:
                    if self.deadline is not None and time.monotonic() >= self.deadline:
                        exploration_complete = False
                        termination_reason = "deadline_exhausted"
                        exploration_status = EXPLORATION_STATUS_BUDGET_EXHAUSTED
                        break
                    if self.max_transitions is not None and transition_count >= self.max_transitions:
                        exploration_complete = False
                        termination_reason = "max_transitions_exhausted"
                        exploration_status = EXPLORATION_STATUS_BUDGET_EXHAUSTED
                        break
                    next_active: list[WorkflowPath] = []
                    for path in active:
                        if self.deadline is not None and time.monotonic() >= self.deadline:
                            exploration_complete = False
                            termination_reason = "deadline_exhausted"
                            exploration_status = EXPLORATION_STATUS_BUDGET_EXHAUSTED
                            break
                        if self.max_transitions is not None and transition_count >= self.max_transitions:
                            exploration_complete = False
                            termination_reason = "max_transitions_exhausted"
                            exploration_status = EXPLORATION_STATUS_BUDGET_EXHAUSTED
                            break
                        transition_count += 1
                        run = self.workflow.execute(
                            initial_state=path.state,
                            external_input=external_input,
                            trace=path.trace.with_external_inputs(sequence),
                            terminal_predicate=self.terminal_predicate,
                        )
                        if compact_trace_storage:
                            dead_room = _COMPACT_FINDING_LIMIT - len(dead_branches)
                            if dead_room > 0:
                                dead_branches.extend(run.dead_branches[:dead_room])
                            exception_room = _COMPACT_FINDING_LIMIT - len(exception_branches)
                            if exception_room > 0:
                                exception_branches.extend(run.exception_branches[:exception_room])
                        else:
                            dead_branches.extend(run.dead_branches)
                            exception_branches.extend(run.exception_branches)
                        observed_failure_count += len(run.dead_branches) + len(run.exception_branches)
                        for completed_path in run.completed_paths:
                            observed_trace_count += 1
                            self._observe_reachability(completed_path, reachability_state)
                            if not compact_trace_storage or len(observed_paths) < 256:
                                observed_paths.append(completed_path)
                            elif self.required_labels:
                                labels = {step.label for step in completed_path.trace.steps}
                                seen = {step.label for path in observed_paths for step in path.trace.steps}
                                if any(label in labels and label not in seen for label in self.required_labels):
                                    observed_paths.append(completed_path)
                            path_violations = self._check_path_invariants(completed_path)
                            observed_failure_count += len(path_violations)
                            if compact_trace_storage:
                                violation_room = _COMPACT_FINDING_LIMIT - len(violations)
                                if violation_room > 0:
                                    violations.extend(path_violations[:violation_room])
                            else:
                                violations.extend(path_violations)
                        next_active.extend(run.completed_paths)
                        if (
                            self.max_failures is not None
                            and observed_failure_count >= self.max_failures
                        ):
                            exploration_complete = False
                            termination_reason = "max_failures_reached"
                            exploration_status = EXPLORATION_STATUS_BUDGET_EXHAUSTED
                            break
                        if (
                            self.failure_witness_limit is not None
                            and observed_failure_count >= self.failure_witness_limit
                            and self._required_obligations_satisfied(reachability_state)
                        ):
                            exploration_complete = False
                            termination_reason = "failure_witness_limit_reached"
                            exploration_status = EXPLORATION_STATUS_STOPPED_ON_COUNTEREXAMPLE
                            break
                    if not exploration_complete:
                        break
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
                            f"traces={observed_trace_count} violations={len(violations)}",
                            file=sys.stderr,
                            flush=True,
                        )
                        next_threshold_index += 1
                if not exploration_complete:
                    break

        traces = tuple(path.trace for path in observed_paths)
        reachability_failures = self._reachability_failures(reachability_state)
        if not self.initial_states or not self.external_inputs:
            reachability_failures.insert(
                0,
                ReachabilityFailure(
                    name="exploration:empty_input_domain",
                    description=(
                        "at least one initial state and one external input are required "
                        "for an exhaustive exploration"
                    ),
                    message=(
                        "no input/state work was executed; empty validation cannot be "
                        "reported as a successful model check"
                    ),
                ),
            )
        ok = (
            exploration_complete
            and not violations
            and not dead_branches
            and not exception_branches
            and not reachability_failures
        )
        summary = (
            f"sequences={sequence_count} initial_states={len(self.initial_states)} "
            f"traces={observed_trace_count}"
        )
        if not exploration_complete:
            summary += (
                f" termination={termination_reason}"
                f" executed_sequences={sequence_started_count}"
                f" transitions={transition_count}"
            )
        remaining_scope = ""
        if not exploration_complete:
            remaining_scope = (
                "unexplored finite input/state scope remains; this result is diagnostic "
                "and cannot be reused as a passing exhaustive check"
            )
        return CheckReport(
            ok=ok,
            violations=tuple(violations),
            traces=traces,
            summary=summary,
            dead_branches=tuple(dead_branches),
            exception_branches=tuple(exception_branches),
            reachability_failures=tuple(reachability_failures),
            explored_sequences=() if compact_trace_storage else tuple(observed_sequences),
            assumption_card=self.assumption_card,
            exploration_complete=exploration_complete,
            termination_reason=termination_reason,
            explored_sequence_count=sequence_started_count,
            transition_count=transition_count,
            remaining_scope=remaining_scope,
            exploration_status=exploration_status,
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

    def _observe_reachability(
        self,
        path: WorkflowPath,
        state: _ReachabilityState,
    ) -> None:
        """Update obligation truth for every completed path.

        Compact storage only bounds retained counterexample/witness paths.  It
        must never bound the set of paths consulted by reachability
        obligations, otherwise a late match can be lost merely because the
        witness cap was reached.
        """

        for index, label in enumerate(self.required_labels):
            if not state.required_label_matches[index] and path.trace.has_label(label):
                state.required_label_matches[index] = True

        if self.success_predicate is not None and not state.success_matched and not state.success_error:
            try:
                state.success_matched = bool(self.success_predicate(path.state, path.trace))
            except Exception as exc:
                state.success_error = f"{type(exc).__name__}: {exc}"

        for index, condition in enumerate(self.required_reachable):
            if state.required_matches[index] or state.required_errors[index]:
                continue
            try:
                state.required_matches[index] = condition.matches(path.state, path.trace)
            except Exception as exc:
                state.required_errors[index] = f"{type(exc).__name__}: {exc}"

    def _reachability_failures(
        self,
        state: _ReachabilityState,
    ) -> list[ReachabilityFailure]:
        failures: list[ReachabilityFailure] = []

        for index, label in enumerate(self.required_labels):
            if not state.required_label_matches[index]:
                failures.append(
                    ReachabilityFailure(
                        name=f"label:{label}",
                        description=f"label {label!r} must be reachable",
                        message=f"no explored trace reached label {label!r}",
                    )
                )

        if self.success_predicate is not None:
            if state.success_error:
                failures.append(
                    ReachabilityFailure(
                        name="success_predicate",
                        description="success predicate raised",
                        message=state.success_error,
                    )
                )
            elif not state.success_matched:
                failures.append(
                    ReachabilityFailure(
                        name="success_predicate",
                        description="at least one success predicate match is required",
                        message="no explored trace matched the success predicate",
                    )
                )

        for index, condition in enumerate(self.required_reachable):
            if state.required_errors[index]:
                failures.append(
                    ReachabilityFailure(
                        name=condition.name,
                        description=condition.description,
                        message=(
                            "reachability predicate raised "
                            + state.required_errors[index]
                        ),
                    )
                )
            elif not state.required_matches[index]:
                failures.append(
                    ReachabilityFailure(
                        name=condition.name,
                        description=condition.description,
                        message=f"required reachable condition was not found: {condition.name}",
                    )
                )

        return failures

    def _required_obligations_satisfied(self, state: _ReachabilityState) -> bool:
        """Allow witness short-circuiting only after declared obligations are observed."""

        if not all(state.required_label_matches):
            return False
        if self.success_predicate is not None and not state.success_matched:
            return False
        if any(state.required_errors) or not all(state.required_matches):
            return False
        return True


__all__ = ["Explorer", "ReachabilityCondition", "enumerate_input_sequences"]
