"""FlowGuard model for AI route handoff continuity.

FlowGuard Risk Purpose Header
Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: review the SummaryReport -> route-owned action -> existing specialist
route handoff before agents use structured next actions for broad claims.
Guards against: report gaps losing owner-route actions, structured handoffs
creating a parallel session runner, or broad confidence being accepted before
owner-route proof evidence exists.
Modeled block shape: Input x State -> Set(Output x State).
Run: python .flowguard/ai_route_handoffs/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


ROUTE_DEVELOPMENT_PROCESS_FLOW = "development_process_flow"
ROUTE_MODEL_MATURATION = "model_maturation_loop"
ROUTE_MODEL_TEST_ALIGNMENT = "model_test_alignment"
FORBIDDEN_SESSION_RUNNER = "ai_session_runner"


@dataclass(frozen=True)
class HandoffInput:
    action_type: str


@dataclass(frozen=True)
class HandoffOutput:
    status: str


@dataclass(frozen=True)
class HandoffState:
    summary_gap_seen: bool = False
    owner_route: str = ""
    action_created: bool = False
    owner_action_bound: bool = False
    specialist_route_seen: bool = False
    owner_proof_seen: bool = False
    final_claim: str = "none"

    def route_is_existing(self) -> bool:
        return self.owner_route in {
            ROUTE_DEVELOPMENT_PROCESS_FLOW,
            ROUTE_MODEL_MATURATION,
            ROUTE_MODEL_TEST_ALIGNMENT,
        }

    def full_claim_allowed(self) -> bool:
        return (
            self.summary_gap_seen
            and self.action_created
            and self.owner_action_bound
            and self.specialist_route_seen
            and self.owner_proof_seen
            and self.route_is_existing()
        )


class CorrectRouteHandoff:
    name = "CorrectRouteHandoff"
    reads = (
        "summary_gap_seen",
        "owner_route",
        "action_created",
        "owner_action_bound",
        "specialist_route_seen",
        "owner_proof_seen",
        "final_claim",
    )
    writes = reads
    accepted_input_type = HandoffInput
    input_description = "AI handoff step"
    output_description = "AI handoff state"
    idempotency = "Summary gaps become existing-route actions and broad claims wait for owner proof."

    def apply(self, input_obj: HandoffInput, state: HandoffState) -> Iterable[FunctionResult]:
        emitted = False
        action = input_obj.action_type
        if action == "summary_conformance_gap":
            emitted = True
            yield FunctionResult(
                HandoffOutput("summary_gap_recorded"),
                replace(
                    state,
                    summary_gap_seen=True,
                    owner_route=ROUTE_DEVELOPMENT_PROCESS_FLOW,
                    final_claim="none",
                ),
                label="summary_gap_recorded",
            )
        elif action == "summary_model_gap":
            emitted = True
            yield FunctionResult(
                HandoffOutput("summary_gap_recorded"),
                replace(
                    state,
                    summary_gap_seen=True,
                    owner_route=ROUTE_MODEL_MATURATION,
                    final_claim="none",
                ),
                label="summary_gap_recorded",
            )
        elif action == "summary_alignment_gap":
            emitted = True
            yield FunctionResult(
                HandoffOutput("summary_gap_recorded"),
                replace(
                    state,
                    summary_gap_seen=True,
                    owner_route=ROUTE_MODEL_TEST_ALIGNMENT,
                    final_claim="none",
                ),
                label="summary_gap_recorded",
            )
        elif action == "bind_owner_action":
            if state.summary_gap_seen and state.route_is_existing():
                emitted = True
                yield FunctionResult(
                    HandoffOutput("owner_action_bound"),
                    replace(state, action_created=True, owner_action_bound=True),
                    label="owner_action_bound",
                )
        elif action == "specialist_route_runs":
            if state.owner_action_bound:
                emitted = True
                yield FunctionResult(
                    HandoffOutput("specialist_route_ran"),
                    replace(state, specialist_route_seen=True),
                    label="specialist_route_ran",
                )
        elif action == "record_owner_proof":
            if state.specialist_route_seen:
                emitted = True
                yield FunctionResult(
                    HandoffOutput("owner_proof_recorded"),
                    replace(state, owner_proof_seen=True),
                    label="owner_proof_recorded",
                )
        elif action == "claim_full":
            emitted = True
            claim = "full" if state.full_claim_allowed() else "scoped"
            yield FunctionResult(
                HandoffOutput(f"claim_{claim}"),
                replace(state, final_claim=claim),
                label=f"claim_{claim}",
            )
        if not emitted:
            yield FunctionResult(
                HandoffOutput("no_op"),
                state,
                label="no_op",
            )


class BrokenSessionRunnerRoute(CorrectRouteHandoff):
    name = "BrokenSessionRunnerRoute"
    idempotency = "Broken variant routes summary gaps to a new parallel session runner."

    def apply(self, input_obj: HandoffInput, state: HandoffState) -> Iterable[FunctionResult]:
        if input_obj.action_type.startswith("summary_"):
            yield FunctionResult(
                HandoffOutput("summary_gap_recorded"),
                replace(
                    state,
                    summary_gap_seen=True,
                    owner_route=FORBIDDEN_SESSION_RUNNER,
                    final_claim="none",
                ),
                label="summary_gap_recorded",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenNoOwnerActionBinding(CorrectRouteHandoff):
    name = "BrokenNoOwnerActionBinding"
    idempotency = "Broken variant creates an action hint without binding it to the selected owner route."

    def apply(self, input_obj: HandoffInput, state: HandoffState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "bind_owner_action" and state.summary_gap_seen:
            yield FunctionResult(
                HandoffOutput("action_hint_created_without_scan"),
                replace(state, action_created=True),
                label="action_hint_created_without_scan",
            )
            return
        if input_obj.action_type == "specialist_route_runs" and state.action_created:
            yield FunctionResult(
                HandoffOutput("specialist_route_ran"),
                replace(state, specialist_route_seen=True),
                label="specialist_route_ran",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenFullClaimWithoutProof(CorrectRouteHandoff):
    name = "BrokenFullClaimWithoutProof"
    idempotency = "Broken variant accepts full confidence before owner-route proof exists."

    def apply(self, input_obj: HandoffInput, state: HandoffState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "claim_full":
            yield FunctionResult(
                HandoffOutput("claim_full"),
                replace(state, final_claim="full"),
                label="claim_full",
            )
            return
        yield from super().apply(input_obj, state)


def terminal_predicate(current_output, state, trace) -> bool:
    del state, trace
    return isinstance(current_output, HandoffOutput) and current_output.status.startswith("claim_")


def summary_gap_gets_existing_owner_route(state: HandoffState, trace) -> InvariantResult:
    del trace
    if state.summary_gap_seen and not state.route_is_existing():
        return InvariantResult.fail("summary gap routed outside existing FlowGuard specialist routes")
    return InvariantResult.pass_()


def action_hint_reaches_selected_owner(state: HandoffState, trace) -> InvariantResult:
    del trace
    if state.specialist_route_seen and not state.owner_action_bound:
        return InvariantResult.fail("specialist route ran without a bound route-owned action")
    return InvariantResult.pass_()


def full_claim_requires_owner_proof(state: HandoffState, trace) -> InvariantResult:
    del trace
    if state.final_claim == "full" and not state.full_claim_allowed():
        return InvariantResult.fail("full claim accepted before existing owner-route proof")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "summary_gap_gets_existing_owner_route",
        "Summary gaps must route to existing FlowGuard specialist routes, not a new session runner.",
        summary_gap_gets_existing_owner_route,
    ),
    Invariant(
        "action_hint_reaches_selected_owner",
        "Structured action hints must bind directly to the selected specialist route before its claims.",
        action_hint_reaches_selected_owner,
    ),
    Invariant(
        "full_claim_requires_owner_proof",
        "Broad full confidence requires owner-route proof evidence.",
        full_claim_requires_owner_proof,
    ),
)

EXTERNAL_INPUTS = (
    HandoffInput("summary_conformance_gap"),
    HandoffInput("bind_owner_action"),
    HandoffInput("specialist_route_runs"),
    HandoffInput("record_owner_proof"),
    HandoffInput("claim_full"),
)

MAX_SEQUENCE_LENGTH = 5


def initial_state() -> HandoffState:
    return HandoffState()


def build_correct_workflow() -> Workflow:
    return Workflow((CorrectRouteHandoff(),), name="ai_route_handoff_correct")


def build_broken_workflows() -> tuple[Workflow, ...]:
    return (
        Workflow((BrokenSessionRunnerRoute(),), name="ai_route_handoff_session_runner"),
        Workflow((BrokenNoOwnerActionBinding(),), name="ai_route_handoff_missing_owner_binding"),
        Workflow((BrokenFullClaimWithoutProof(),), name="ai_route_handoff_proof_gap"),
    )


__all__ = [
    "EXTERNAL_INPUTS",
    "INVARIANTS",
    "MAX_SEQUENCE_LENGTH",
    "HandoffInput",
    "HandoffOutput",
    "HandoffState",
    "build_broken_workflows",
    "build_correct_workflow",
    "initial_state",
    "terminal_predicate",
]
