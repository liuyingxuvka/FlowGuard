"""Scenario sandbox execution for exact input sequences."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

from .core import FrozenMetadata, InvariantResult, freeze_metadata
from .export import to_json_text, to_jsonable
from .report import CheckReport, DeadBranch, ExceptionBranch, InvariantViolation
from .trace import Trace
from .workflow import Workflow, WorkflowPath


OracleCheck = Callable[["ScenarioRun"], "OracleCheckResult"]


@dataclass(frozen=True)
class OracleCheckResult:
    """Result from a scenario-specific oracle check."""

    ok: bool
    message: str = ""
    evidence: tuple[str, ...] = ()
    violation_name: str = "oracle_mismatch"
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "ok", bool(self.ok))
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))


@dataclass(frozen=True)
class ScenarioExpectation:
    """Human oracle for one scenario."""

    expected_status: str = "ok"
    expected_violation_names: tuple[str, ...] = ()
    required_trace_labels: tuple[str, ...] = ()
    forbidden_trace_labels: tuple[str, ...] = ()
    required_evidence: tuple[str, ...] = ()
    custom_checks: tuple[OracleCheck, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "expected_status", self.expected_status.lower())
        object.__setattr__(self, "expected_violation_names", tuple(self.expected_violation_names))
        object.__setattr__(self, "required_trace_labels", tuple(self.required_trace_labels))
        object.__setattr__(self, "forbidden_trace_labels", tuple(self.forbidden_trace_labels))
        object.__setattr__(self, "required_evidence", tuple(self.required_evidence))
        object.__setattr__(self, "custom_checks", tuple(self.custom_checks))


@dataclass(frozen=True)
class Scenario:
    """A deterministic, human-designed test condition."""

    name: str
    description: str
    initial_state: Any
    external_input_sequence: tuple[Any, ...]
    expected: ScenarioExpectation
    tags: tuple[str, ...] = ()
    notes: str = ""
    workflow: Workflow | None = None
    invariants: tuple[Any, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "external_input_sequence", tuple(self.external_input_sequence))
        object.__setattr__(self, "tags", tuple(self.tags))
        object.__setattr__(self, "invariants", tuple(self.invariants))


@dataclass(frozen=True)
class ScenarioRun:
    """Observed result from executing one scenario."""

    scenario: Scenario
    model_report: CheckReport
    traces: tuple[Trace, ...]
    final_states: tuple[Any, ...]
    observed_status: str
    observed_violation_names: tuple[str, ...]
    evidence: tuple[str, ...] = ()
    oracle_check_results: tuple[OracleCheckResult, ...] = ()
    conformance_report: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": {
                "name": self.scenario.name,
                "description": self.scenario.description,
                "tags": list(self.scenario.tags),
                "notes": self.scenario.notes,
                "external_input_sequence": to_jsonable(self.scenario.external_input_sequence),
                "expected": {
                    "expected_status": self.scenario.expected.expected_status,
                    "expected_violation_names": list(
                        self.scenario.expected.expected_violation_names
                    ),
                    "required_trace_labels": list(
                        self.scenario.expected.required_trace_labels
                    ),
                    "forbidden_trace_labels": list(
                        self.scenario.expected.forbidden_trace_labels
                    ),
                    "summary": self.scenario.expected.summary,
                },
            },
            "observed_status": self.observed_status,
            "observed_violation_names": list(self.observed_violation_names),
            "evidence": list(self.evidence),
            "final_states": to_jsonable(self.final_states),
            "traces": [trace.to_dict() for trace in self.traces],
            "model_report": self.model_report.to_dict(),
            "oracle_check_results": [
                {
                    "ok": result.ok,
                    "message": result.message,
                    "evidence": list(result.evidence),
                    "violation_name": result.violation_name,
                    "metadata": to_jsonable(result.metadata),
                }
                for result in self.oracle_check_results
            ],
        }

    def to_json_text(self, indent: int = 2) -> str:
        return to_json_text(self.to_dict(), indent=indent)


def _invariant_name(invariant: Any) -> str:
    return str(getattr(invariant, "name", getattr(invariant, "__name__", type(invariant).__name__)))


def _invariant_description(invariant: Any) -> str:
    return str(getattr(invariant, "description", ""))


def _check_invariant(invariant: Any, state: Any, trace: Trace) -> InvariantResult:
    check = getattr(invariant, "check", None)
    try:
        result = check(state, trace) if check is not None else invariant(state, trace)
    except Exception as exc:
        return InvariantResult.fail(f"invariant raised {type(exc).__name__}: {exc}")
    if isinstance(result, InvariantResult):
        return result
    if bool(result):
        return InvariantResult.pass_()
    return InvariantResult.fail(f"invariant failed: {_invariant_name(invariant)}")


def _collect_violations(
    invariants: Sequence[Any],
    state: Any,
    trace: Trace,
) -> list[InvariantViolation]:
    violations: list[InvariantViolation] = []
    for invariant in invariants:
        result = _check_invariant(invariant, state, trace)
        if result.ok:
            continue
        violations.append(
            InvariantViolation(
                invariant_name=_invariant_name(invariant),
                description=_invariant_description(invariant),
                message=result.message,
                state=state,
                trace=trace,
                metadata=result.metadata,
            )
        )
    return violations


def _observed_status(report: CheckReport) -> str:
    if report.exception_branches:
        return "exception"
    if report.dead_branches:
        return "dead_branch"
    if report.violations:
        return "violation"
    return "ok"


def _observed_violation_names(report: CheckReport) -> tuple[str, ...]:
    names = [violation.invariant_name for violation in report.violations]
    if report.dead_branches:
        names.append("dead_branch")
    if report.exception_branches:
        names.append("exception")
    return tuple(dict.fromkeys(names))


def _default_evidence(report: CheckReport, final_states: Sequence[Any]) -> tuple[str, ...]:
    evidence = [
        f"traces={len(report.traces)}",
        f"final_states={len(final_states)}",
        f"violations={len(report.violations)}",
        f"dead_branches={len(report.dead_branches)}",
        f"exceptions={len(report.exception_branches)}",
    ]
    if report.violations:
        evidence.append(
            "violation_names="
            + ",".join(_observed_violation_names(report))
        )
    return tuple(evidence)


def run_exact_sequence(
    workflow: Workflow,
    initial_state: Any,
    external_input_sequence: Sequence[Any],
    invariants: Sequence[Any] = (),
    scenario: Scenario | None = None,
) -> ScenarioRun:
    """Execute one exact external input sequence through a workflow."""

    sequence = tuple(external_input_sequence)
    base_trace = Trace(initial_state=initial_state, external_inputs=sequence)
    violations: list[InvariantViolation] = []
    dead_branches: list[DeadBranch] = []
    exception_branches: list[ExceptionBranch] = []
    final_paths: tuple[WorkflowPath, ...] = ()

    violations.extend(_collect_violations(invariants, initial_state, base_trace))

    active = (
        WorkflowPath(
            current_input=None,
            state=initial_state,
            trace=base_trace,
        ),
    )

    if not sequence:
        final_paths = active
        violations.extend(_collect_violations(invariants, initial_state, base_trace))
    else:
        for index, external_input in enumerate(sequence):
            next_active: list[WorkflowPath] = []
            for path in active:
                run = workflow.execute(
                    initial_state=path.state,
                    external_input=external_input,
                    trace=path.trace.with_external_inputs(sequence),
                )
                dead_branches.extend(run.dead_branches)
                exception_branches.extend(run.exception_branches)
                for completed_path in run.completed_paths:
                    violations.extend(
                        _collect_violations(invariants, completed_path.state, completed_path.trace)
                    )
                next_active.extend(run.completed_paths)
            active = tuple(next_active)
            if index == len(sequence) - 1:
                final_paths = active
            if not active:
                break

    traces = tuple(path.trace for path in final_paths)
    final_states = tuple(path.state for path in active) if sequence else (initial_state,)
    report = CheckReport(
        ok=not violations and not dead_branches and not exception_branches,
        violations=tuple(violations),
        traces=traces,
        summary=f"exact_sequence_length={len(sequence)} traces={len(traces)}",
        dead_branches=tuple(dead_branches),
        exception_branches=tuple(exception_branches),
        explored_sequences=(sequence,),
    )

    if scenario is None:
        scenario = Scenario(
            name="anonymous",
            description="Anonymous exact sequence",
            initial_state=initial_state,
            external_input_sequence=sequence,
            expected=ScenarioExpectation(),
            workflow=workflow,
            invariants=tuple(invariants),
        )

    oracle_results = tuple(check(ScenarioRun(
        scenario=scenario,
        model_report=report,
        traces=traces,
        final_states=final_states,
        observed_status=_observed_status(report),
        observed_violation_names=_observed_violation_names(report),
        evidence=_default_evidence(report, final_states),
    )) for check in scenario.expected.custom_checks)
    custom_violation_names = tuple(
        result.violation_name for result in oracle_results if not result.ok
    )
    observed_names = tuple(dict.fromkeys(_observed_violation_names(report) + custom_violation_names))
    evidence = _default_evidence(report, final_states) + tuple(
        item
        for result in oracle_results
        for item in result.evidence
    )
    observed_status = _observed_status(report)
    if observed_status == "ok" and custom_violation_names:
        observed_status = "violation"

    return ScenarioRun(
        scenario=scenario,
        model_report=report,
        traces=traces,
        final_states=final_states,
        observed_status=observed_status,
        observed_violation_names=observed_names,
        evidence=evidence,
        oracle_check_results=oracle_results,
    )


__all__ = [
    "OracleCheck",
    "OracleCheckResult",
    "Scenario",
    "ScenarioExpectation",
    "ScenarioRun",
    "run_exact_sequence",
]
