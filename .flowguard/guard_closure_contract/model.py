"""FlowGuard model for Guard-family closure reports.

Purpose: ensure a final completion claim only follows a clean child-Guard
closure report. Partial, blocked, downgraded, stale, skipped, missing, or
hard-finding reports must remain maintenance obligations with next actions.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


@dataclass(frozen=True)
class ClosureReportInput:
    report_id: str
    closure_status: str
    hard_findings: bool = False
    missing_inputs: bool = False
    stale_evidence: bool = False
    skipped_checks: bool = False
    has_next_actions: bool = False


@dataclass(frozen=True)
class ClosureAccepted:
    report_id: str


@dataclass(frozen=True)
class MaintenanceObligation:
    report_id: str
    reason: str


@dataclass(frozen=True)
class DoneClaim:
    report_id: str


@dataclass(frozen=True)
class ScopedClaim:
    report_id: str
    reason: str


@dataclass(frozen=True)
class State:
    clean_reports: tuple[str, ...] = ()
    obligations: tuple[str, ...] = ()
    done_claims: tuple[str, ...] = ()
    scoped_claims: tuple[str, ...] = ()


def _clean(report: ClosureReportInput) -> bool:
    return (
        report.closure_status == "passed"
        and not report.hard_findings
        and not report.missing_inputs
        and not report.stale_evidence
        and not report.skipped_checks
    )


class ReviewClosureReport:
    name = "ReviewClosureReport"
    reads = ("clean_reports", "obligations")
    writes = ("clean_reports", "obligations")
    accepted_input_type = ClosureReportInput
    input_description = "Guard-family closure report summary"
    output_description = "ClosureAccepted or MaintenanceObligation"
    idempotency = "Reviewing the same report preserves the same clean/obligation classification."

    def apply(self, input_obj: ClosureReportInput, state: State) -> Iterable[FunctionResult]:
        if _clean(input_obj):
            yield FunctionResult(
                output=ClosureAccepted(input_obj.report_id),
                new_state=replace(state, clean_reports=state.clean_reports + (input_obj.report_id,)),
                label="clean_closure_report",
            )
            return
        if input_obj.closure_status != "passed" and not input_obj.has_next_actions:
            reason = "non_pass_without_next_actions"
            label = "obligation_missing_next_action"
        elif input_obj.stale_evidence:
            reason = "stale_evidence"
            label = "obligation_stale_evidence"
        elif input_obj.skipped_checks:
            reason = "skipped_checks"
            label = "obligation_skipped_checks"
        elif input_obj.hard_findings:
            reason = "hard_findings"
            label = "obligation_hard_findings"
        elif input_obj.missing_inputs:
            reason = "missing_inputs"
            label = "obligation_missing_inputs"
        else:
            reason = "non_pass_closure"
            label = "obligation_non_pass"
        yield FunctionResult(
            output=MaintenanceObligation(input_obj.report_id, reason),
            new_state=replace(state, obligations=state.obligations + (input_obj.report_id,)),
            label=label,
        )


class ClaimCompletion:
    name = "ClaimCompletion"
    reads = ("clean_reports", "obligations")
    writes = ("done_claims", "scoped_claims")
    accepted_input_type = ClosureAccepted
    input_description = "ClosureAccepted"
    output_description = "DoneClaim or ScopedClaim"
    idempotency = "Completion can be claimed only for accepted clean reports."

    def apply(self, input_obj: ClosureAccepted, state: State) -> Iterable[FunctionResult]:
        if input_obj.report_id in state.clean_reports and input_obj.report_id not in state.obligations:
            yield FunctionResult(
                output=DoneClaim(input_obj.report_id),
                new_state=replace(state, done_claims=state.done_claims + (input_obj.report_id,)),
                label="done_claim_allowed",
            )
            return
        yield FunctionResult(
            output=ScopedClaim(input_obj.report_id, "not_clean"),
            new_state=replace(state, scoped_claims=state.scoped_claims + (input_obj.report_id,)),
            label="done_claim_scoped",
        )


def terminal_predicate(current_output, state, trace) -> bool:
    del state, trace
    return isinstance(current_output, (DoneClaim, MaintenanceObligation, ScopedClaim))


def no_done_claim_from_obligation(state: State, trace) -> InvariantResult:
    del trace
    overlap = set(state.done_claims) & set(state.obligations)
    if overlap:
        return InvariantResult.fail(f"done claim from obligated report: {sorted(overlap)!r}")
    return InvariantResult.pass_()


def all_non_pass_reports_have_next_action(state: State, trace) -> InvariantResult:
    del state
    violations = [
        step.function_output.report_id
        for step in trace.steps
        if step.label == "obligation_missing_next_action"
    ]
    if violations:
        return InvariantResult.fail(f"non-pass closure missing next action: {violations!r}")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        name="no_done_claim_from_obligation",
        description="A report with an open maintenance obligation cannot support a done claim.",
        predicate=no_done_claim_from_obligation,
    ),
    Invariant(
        name="all_non_pass_reports_have_next_action",
        description="Partial, blocked, or downgraded reports must expose next actions.",
        predicate=all_non_pass_reports_have_next_action,
    ),
)


EXTERNAL_INPUTS = (
    ClosureReportInput("clean", "passed"),
    ClosureReportInput("partial_routed", "partial", has_next_actions=True),
    ClosureReportInput("dirty_pass_stale", "passed", stale_evidence=True, has_next_actions=True),
)

MAX_SEQUENCE_LENGTH = 2


def initial_state() -> State:
    return State()


def build_workflow() -> Workflow:
    return Workflow((ReviewClosureReport(), ClaimCompletion()), name="guard_closure_contract")


__all__ = [
    "EXTERNAL_INPUTS",
    "INVARIANTS",
    "MAX_SEQUENCE_LENGTH",
    "ClosureAccepted",
    "ClosureReportInput",
    "DoneClaim",
    "MaintenanceObligation",
    "ScopedClaim",
    "State",
    "build_workflow",
    "initial_state",
    "terminal_predicate",
]
