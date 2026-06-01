"""FlowGuard model for the maintenance scan router.

FlowGuard Risk Purpose Header
Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: review the thin maintenance scan route before agents use it to close
FlowGuard-managed project work.
Guards against: model/code/test drift being treated as done, skipped candidate
routes disappearing, split pressure being ignored, or a broad completion claim
being accepted before owner-route evidence exists.
Modeled block shape: Input x State -> Set(Output x State).
Run: python .flowguard/maintenance_scan_router/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


ROUTE_MODEL_TEST_ALIGNMENT = "model_test_alignment"
ROUTE_STRUCTURE_MESH = "structure_mesh_maintenance"
ROUTE_AGENT_WORKFLOW_REHEARSAL = "agent_workflow_rehearsal"


@dataclass(frozen=True)
class MaintenanceScanInput:
    action_type: str


@dataclass(frozen=True)
class MaintenanceScanOutput:
    status: str


@dataclass(frozen=True)
class MaintenanceScanState:
    model_code_test_changed: bool = False
    large_module_signal: bool = False
    unaccepted_route_skip: bool = False
    required_routes: tuple[str, ...] = ()
    owner_evidence_routes: tuple[str, ...] = ()
    broad_claim: str = "none"

    def unresolved_routes(self) -> tuple[str, ...]:
        return tuple(route for route in self.required_routes if route not in self.owner_evidence_routes)

    def full_claim_allowed(self) -> bool:
        return not self.unresolved_routes()


def _append_once(values: tuple[str, ...], value: str) -> tuple[str, ...]:
    return values if value in values else values + (value,)


class CorrectMaintenanceScanRouter:
    name = "CorrectMaintenanceScanRouter"
    reads = (
        "model_code_test_changed",
        "large_module_signal",
        "unaccepted_route_skip",
        "required_routes",
        "owner_evidence_routes",
        "broad_claim",
    )
    writes = reads
    accepted_input_type = MaintenanceScanInput
    input_description = "maintenance scan observation or claim"
    output_description = "maintenance scan route state"
    idempotency = "Repeated observations keep one required owner route, and broad full claims wait for owner-route evidence."

    def apply(self, input_obj: MaintenanceScanInput, state: MaintenanceScanState) -> Iterable[FunctionResult]:
        action = input_obj.action_type
        if action == "observe_model_code_test_change":
            yield FunctionResult(
                MaintenanceScanOutput("model_test_alignment_routed"),
                replace(
                    state,
                    model_code_test_changed=True,
                    required_routes=_append_once(state.required_routes, ROUTE_MODEL_TEST_ALIGNMENT),
                    broad_claim="none",
                ),
                label="model_test_alignment_routed",
            )
        elif action == "observe_large_module":
            yield FunctionResult(
                MaintenanceScanOutput("structure_mesh_routed"),
                replace(
                    state,
                    large_module_signal=True,
                    required_routes=_append_once(state.required_routes, ROUTE_STRUCTURE_MESH),
                    broad_claim="none",
                ),
                label="structure_mesh_routed",
            )
        elif action == "observe_unaccepted_skip":
            yield FunctionResult(
                MaintenanceScanOutput("agent_workflow_rehearsal_routed"),
                replace(
                    state,
                    unaccepted_route_skip=True,
                    required_routes=_append_once(state.required_routes, ROUTE_AGENT_WORKFLOW_REHEARSAL),
                    broad_claim="none",
                ),
                label="agent_workflow_rehearsal_routed",
            )
        elif action == "record_owner_evidence":
            yield FunctionResult(
                MaintenanceScanOutput("owner_evidence_recorded"),
                replace(state, owner_evidence_routes=state.required_routes),
                label="owner_evidence_recorded",
            )
        elif action == "claim_broad_done":
            if state.full_claim_allowed():
                yield FunctionResult(
                    MaintenanceScanOutput("full_claim_accepted"),
                    replace(state, broad_claim="full_accepted"),
                    label="full_claim_accepted",
                )
            else:
                yield FunctionResult(
                    MaintenanceScanOutput("scoped_claim_only"),
                    replace(state, broad_claim="scoped_only"),
                    label="scoped_claim_only",
                )


class BrokenNoModelAlignment(CorrectMaintenanceScanRouter):
    name = "BrokenNoModelAlignment"
    idempotency = "Broken variant observes model/code/test drift without routing to model-test alignment."

    def apply(self, input_obj: MaintenanceScanInput, state: MaintenanceScanState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "observe_model_code_test_change":
            yield FunctionResult(
                MaintenanceScanOutput("model_code_test_observed_without_route"),
                replace(state, model_code_test_changed=True, broad_claim="none"),
                label="model_code_test_observed_without_route",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenNoStructureRoute(CorrectMaintenanceScanRouter):
    name = "BrokenNoStructureRoute"
    idempotency = "Broken variant observes split pressure without routing to StructureMesh."

    def apply(self, input_obj: MaintenanceScanInput, state: MaintenanceScanState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "observe_large_module":
            yield FunctionResult(
                MaintenanceScanOutput("large_module_observed_without_route"),
                replace(state, large_module_signal=True, broad_claim="none"),
                label="large_module_observed_without_route",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenSkipDrop(CorrectMaintenanceScanRouter):
    name = "BrokenSkipDrop"
    idempotency = "Broken variant records skipped route pressure without rehearsal routing."

    def apply(self, input_obj: MaintenanceScanInput, state: MaintenanceScanState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "observe_unaccepted_skip":
            yield FunctionResult(
                MaintenanceScanOutput("skip_observed_without_route"),
                replace(state, unaccepted_route_skip=True, broad_claim="none"),
                label="skip_observed_without_route",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenBroadClaim(CorrectMaintenanceScanRouter):
    name = "BrokenBroadClaim"
    idempotency = "Broken variant accepts broad done while required maintenance routes are unresolved."

    def apply(self, input_obj: MaintenanceScanInput, state: MaintenanceScanState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "claim_broad_done":
            yield FunctionResult(
                MaintenanceScanOutput("full_claim_accepted"),
                replace(state, broad_claim="full_accepted"),
                label="full_claim_accepted",
            )
            return
        yield from super().apply(input_obj, state)


def terminal_predicate(current_output, state, trace) -> bool:
    del state, trace
    return isinstance(current_output, MaintenanceScanOutput) and current_output.status in {
        "full_claim_accepted",
        "scoped_claim_only",
    }


def model_code_test_change_routes_alignment(state: MaintenanceScanState, trace) -> InvariantResult:
    del trace
    if state.model_code_test_changed and ROUTE_MODEL_TEST_ALIGNMENT not in state.required_routes:
        return InvariantResult.fail("model/code/test drift did not route to model-test alignment")
    return InvariantResult.pass_()


def large_module_routes_structure_mesh(state: MaintenanceScanState, trace) -> InvariantResult:
    del trace
    if state.large_module_signal and ROUTE_STRUCTURE_MESH not in state.required_routes:
        return InvariantResult.fail("large-module split pressure did not route to StructureMesh")
    return InvariantResult.pass_()


def unaccepted_skip_routes_workflow_rehearsal(state: MaintenanceScanState, trace) -> InvariantResult:
    del trace
    if state.unaccepted_route_skip and ROUTE_AGENT_WORKFLOW_REHEARSAL not in state.required_routes:
        return InvariantResult.fail("unaccepted skipped route did not route to AgentWorkflowRehearsal")
    return InvariantResult.pass_()


def broad_claim_requires_owner_evidence(state: MaintenanceScanState, trace) -> InvariantResult:
    del trace
    if state.broad_claim == "full_accepted" and state.unresolved_routes():
        return InvariantResult.fail("broad full claim accepted with unresolved maintenance routes")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "model_code_test_change_routes_alignment",
        "Changed model/code/test boundaries require the model-test alignment route.",
        model_code_test_change_routes_alignment,
    ),
    Invariant(
        "large_module_routes_structure_mesh",
        "Large module or split pressure requires the StructureMesh route.",
        large_module_routes_structure_mesh,
    ),
    Invariant(
        "unaccepted_skip_routes_workflow_rehearsal",
        "Unaccepted skipped candidate routes require AgentWorkflowRehearsal.",
        unaccepted_skip_routes_workflow_rehearsal,
    ),
    Invariant(
        "broad_claim_requires_owner_evidence",
        "Broad completion cannot be accepted while required maintenance routes are unresolved.",
        broad_claim_requires_owner_evidence,
    ),
)

EXTERNAL_INPUTS = (
    MaintenanceScanInput("observe_model_code_test_change"),
    MaintenanceScanInput("observe_large_module"),
    MaintenanceScanInput("observe_unaccepted_skip"),
    MaintenanceScanInput("record_owner_evidence"),
    MaintenanceScanInput("claim_broad_done"),
)

MAX_SEQUENCE_LENGTH = 5


def initial_state() -> MaintenanceScanState:
    return MaintenanceScanState()


def build_correct_workflow() -> Workflow:
    return Workflow((CorrectMaintenanceScanRouter(),), name="maintenance_scan_router_correct")


def build_broken_workflows() -> tuple[Workflow, ...]:
    return (
        Workflow((BrokenNoModelAlignment(),), name="maintenance_scan_missing_alignment"),
        Workflow((BrokenNoStructureRoute(),), name="maintenance_scan_missing_structure"),
        Workflow((BrokenSkipDrop(),), name="maintenance_scan_missing_rehearsal"),
        Workflow((BrokenBroadClaim(),), name="maintenance_scan_bad_claim"),
    )


__all__ = [
    "EXTERNAL_INPUTS",
    "INVARIANTS",
    "MAX_SEQUENCE_LENGTH",
    "MaintenanceScanInput",
    "MaintenanceScanOutput",
    "MaintenanceScanState",
    "build_broken_workflows",
    "build_correct_workflow",
    "initial_state",
    "terminal_predicate",
]
