"""FlowGuard model for maintenance obligation memory.

FlowGuard Risk Purpose Header
Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: ensure remembered FlowGuard maintenance gaps are inherited by existing
routes instead of becoming a separate debt-hunting workflow.
Guards against: anchored obligations disappearing, unanchored observations
blocking unrelated work, self-resolved debt memory, and broad confidence claims
before owner-route evidence exists.
Modeled block shape: Input x State -> Set(Output x State).
Run: python .flowguard/maintenance_obligation_memory/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


STATUS_NONE = "none"
STATUS_OPEN = "open"
STATUS_RESOLVED = "resolved"
STATUS_SCOPED = "scoped"
STATUS_OBSERVATION = "observation"

ROUTE_NONE = "none"
ROUTE_OWNER = "owner_route"
ROUTE_UNANCHORED = "unanchored_observation"


@dataclass(frozen=True)
class ObligationMemoryInput:
    action_type: str


@dataclass(frozen=True)
class ObligationMemoryOutput:
    status: str


@dataclass(frozen=True)
class ObligationMemoryState:
    obligation_status: str = STATUS_NONE
    anchor_recorded: bool = False
    anchor_touched: bool = False
    route_reason: str = ROUTE_NONE
    owner_evidence_current: bool = False
    scope_reason_recorded: bool = False
    broad_claim: str = "none"

    def unresolved_for_full_claim(self) -> bool:
        if self.obligation_status == STATUS_OPEN:
            return True
        if self.obligation_status == STATUS_SCOPED:
            return True
        if self.obligation_status == STATUS_RESOLVED and not self.owner_evidence_current:
            return True
        return False


class CorrectObligationMemory:
    name = "CorrectObligationMemory"
    reads = (
        "obligation_status",
        "anchor_recorded",
        "anchor_touched",
        "route_reason",
        "owner_evidence_current",
        "scope_reason_recorded",
        "broad_claim",
    )
    writes = reads
    accepted_input_type = ObligationMemoryInput
    input_description = "maintenance obligation memory event"
    output_description = "remembered obligation state"
    idempotency = "Anchored open obligations route to the owner route; unanchored observations remain non-blocking memory."

    def apply(self, input_obj: ObligationMemoryInput, state: ObligationMemoryState) -> Iterable[FunctionResult]:
        action = input_obj.action_type
        if action == "record_anchored_obligation":
            yield FunctionResult(
                ObligationMemoryOutput("anchored_obligation_recorded"),
                replace(
                    state,
                    obligation_status=STATUS_OPEN,
                    anchor_recorded=True,
                    route_reason=ROUTE_OWNER,
                    broad_claim="none",
                ),
                label="anchored_obligation_recorded",
            )
        elif action == "record_unanchored_observation":
            yield FunctionResult(
                ObligationMemoryOutput("unanchored_observation_recorded"),
                replace(
                    state,
                    obligation_status=STATUS_OBSERVATION,
                    anchor_recorded=False,
                    route_reason=ROUTE_NONE,
                    broad_claim="none",
                ),
                label="unanchored_observation_recorded",
            )
        elif action == "touch_anchor":
            route_reason = ROUTE_OWNER if state.obligation_status == STATUS_OPEN and state.anchor_recorded else state.route_reason
            yield FunctionResult(
                ObligationMemoryOutput("anchor_touched"),
                replace(state, anchor_touched=True, route_reason=route_reason, broad_claim="none"),
                label="anchor_touched",
            )
        elif action == "record_owner_evidence":
            yield FunctionResult(
                ObligationMemoryOutput("owner_evidence_recorded"),
                replace(
                    state,
                    obligation_status=STATUS_RESOLVED if state.route_reason == ROUTE_OWNER else state.obligation_status,
                    owner_evidence_current=True,
                    broad_claim="none",
                ),
                label="owner_evidence_recorded",
            )
        elif action == "scope_obligation":
            yield FunctionResult(
                ObligationMemoryOutput("obligation_scoped"),
                replace(
                    state,
                    obligation_status=STATUS_SCOPED if state.route_reason == ROUTE_OWNER else state.obligation_status,
                    scope_reason_recorded=True,
                    broad_claim="none",
                ),
                label="obligation_scoped",
            )
        elif action == "claim_broad_done":
            if state.unresolved_for_full_claim():
                yield FunctionResult(
                    ObligationMemoryOutput("scoped_claim_only"),
                    replace(state, broad_claim="scoped_only"),
                    label="scoped_claim_only",
                )
            else:
                yield FunctionResult(
                    ObligationMemoryOutput("full_claim_accepted"),
                    replace(state, broad_claim="full_accepted"),
                    label="full_claim_accepted",
                )


class BrokenDropsAnchoredRoute(CorrectObligationMemory):
    name = "BrokenDropsAnchoredRoute"
    idempotency = "Broken variant records an anchored open obligation without the owner route."

    def apply(self, input_obj: ObligationMemoryInput, state: ObligationMemoryState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "record_anchored_obligation":
            yield FunctionResult(
                ObligationMemoryOutput("anchored_without_owner_route"),
                replace(state, obligation_status=STATUS_OPEN, anchor_recorded=True, route_reason=ROUTE_NONE),
                label="anchored_without_owner_route",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenObservationHardGate(CorrectObligationMemory):
    name = "BrokenObservationHardGate"
    idempotency = "Broken variant turns an unanchored observation into a hard owner-route gate."

    def apply(self, input_obj: ObligationMemoryInput, state: ObligationMemoryState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "record_unanchored_observation":
            yield FunctionResult(
                ObligationMemoryOutput("unanchored_observation_hard_gated"),
                replace(state, obligation_status=STATUS_OBSERVATION, route_reason=ROUTE_UNANCHORED),
                label="unanchored_observation_hard_gated",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenSelfResolve(CorrectObligationMemory):
    name = "BrokenSelfResolve"
    idempotency = "Broken variant marks an anchored obligation resolved without owner-route evidence."

    def apply(self, input_obj: ObligationMemoryInput, state: ObligationMemoryState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "record_anchored_obligation":
            yield FunctionResult(
                ObligationMemoryOutput("self_resolved_without_evidence"),
                replace(
                    state,
                    obligation_status=STATUS_RESOLVED,
                    anchor_recorded=True,
                    route_reason=ROUTE_OWNER,
                    owner_evidence_current=False,
                ),
                label="self_resolved_without_evidence",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenBroadClaim(CorrectObligationMemory):
    name = "BrokenBroadClaim"
    idempotency = "Broken variant accepts broad confidence while obligation memory is unresolved."

    def apply(self, input_obj: ObligationMemoryInput, state: ObligationMemoryState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "claim_broad_done":
            yield FunctionResult(
                ObligationMemoryOutput("full_claim_accepted"),
                replace(state, broad_claim="full_accepted"),
                label="full_claim_accepted",
            )
            return
        yield from super().apply(input_obj, state)


def terminal_predicate(current_output, state, trace) -> bool:
    del state, trace
    return isinstance(current_output, ObligationMemoryOutput) and current_output.status in {
        "full_claim_accepted",
        "scoped_claim_only",
    }


def anchored_obligation_routes_owner(state: ObligationMemoryState, trace) -> InvariantResult:
    del trace
    if state.obligation_status == STATUS_OPEN and state.anchor_recorded and state.route_reason != ROUTE_OWNER:
        return InvariantResult.fail("anchored open obligation did not route to the owner route")
    return InvariantResult.pass_()


def unanchored_observation_is_not_hard_gate(state: ObligationMemoryState, trace) -> InvariantResult:
    del trace
    if state.obligation_status == STATUS_OBSERVATION and state.route_reason == ROUTE_UNANCHORED:
        return InvariantResult.fail("unanchored observation became a hard route gate")
    return InvariantResult.pass_()


def resolved_obligation_requires_owner_evidence(state: ObligationMemoryState, trace) -> InvariantResult:
    del trace
    if state.obligation_status == STATUS_RESOLVED and state.route_reason == ROUTE_OWNER and not state.owner_evidence_current:
        return InvariantResult.fail("maintenance obligation resolved without owner-route evidence")
    return InvariantResult.pass_()


def broad_claim_requires_closed_memory(state: ObligationMemoryState, trace) -> InvariantResult:
    del trace
    if state.broad_claim == "full_accepted" and state.unresolved_for_full_claim():
        return InvariantResult.fail("broad full claim accepted while obligation memory is unresolved")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "anchored_obligation_routes_owner",
        "Anchored open obligations must route through their existing owner route.",
        anchored_obligation_routes_owner,
    ),
    Invariant(
        "unanchored_observation_is_not_hard_gate",
        "Unanchored observations remain memory, not hard gates on unrelated work.",
        unanchored_observation_is_not_hard_gate,
    ),
    Invariant(
        "resolved_obligation_requires_owner_evidence",
        "Maintenance obligation memory cannot mark itself resolved without owner-route evidence.",
        resolved_obligation_requires_owner_evidence,
    ),
    Invariant(
        "broad_claim_requires_closed_memory",
        "Broad confidence requires open/scoped obligations to be closed by owner evidence.",
        broad_claim_requires_closed_memory,
    ),
)

EXTERNAL_INPUTS = (
    ObligationMemoryInput("record_anchored_obligation"),
    ObligationMemoryInput("record_unanchored_observation"),
    ObligationMemoryInput("touch_anchor"),
    ObligationMemoryInput("record_owner_evidence"),
    ObligationMemoryInput("scope_obligation"),
    ObligationMemoryInput("claim_broad_done"),
)

MAX_SEQUENCE_LENGTH = 5


def initial_state() -> ObligationMemoryState:
    return ObligationMemoryState()


def build_correct_workflow() -> Workflow:
    return Workflow((CorrectObligationMemory(),), name="maintenance_obligation_memory_correct")


def build_broken_workflows() -> tuple[Workflow, ...]:
    return (
        Workflow((BrokenDropsAnchoredRoute(),), name="maintenance_obligation_missing_owner_route"),
        Workflow((BrokenObservationHardGate(),), name="maintenance_obligation_hard_gated_observation"),
        Workflow((BrokenSelfResolve(),), name="maintenance_obligation_self_resolved"),
        Workflow((BrokenBroadClaim(),), name="maintenance_obligation_bad_claim"),
    )


__all__ = [
    "EXTERNAL_INPUTS",
    "INVARIANTS",
    "MAX_SEQUENCE_LENGTH",
    "ObligationMemoryInput",
    "ObligationMemoryOutput",
    "ObligationMemoryState",
    "build_broken_workflows",
    "build_correct_workflow",
    "initial_state",
    "terminal_predicate",
]
