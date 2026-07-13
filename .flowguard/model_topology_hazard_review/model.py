"""FlowGuard model for model-topology hazard review.

FlowGuard Risk Purpose Header
Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: ensure experienced-engineer future-risk inference is grounded in model
topology before it affects confidence.
Guards against: generic unanchored AI warnings acting as hard gates, topology
hazards staying as prose only, compatibility history lacking a disposition, and
full confidence before anchored future-use hazards are handled or scoped.
Modeled block shape: Input x State -> Set(Output x State).
Run: python .flowguard/model_topology_hazard_review/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


@dataclass(frozen=True)
class TopologyHazardInput:
    action_type: str


@dataclass(frozen=True)
class TopologyHazardOutput:
    status: str


@dataclass(frozen=True)
class TopologyHazardState:
    topology_anchor_present: bool = False
    future_hazard_inferred: bool = False
    hard_gate_without_anchor: bool = False
    required_route_created: bool = False
    hazard_handled_or_scoped: bool = False
    legacy_history_possible: bool = False
    compatibility_disposition: bool = False
    final_claim: str = "none"

    def full_claim_allowed(self) -> bool:
        if self.hard_gate_without_anchor:
            return False
        if self.future_hazard_inferred and not self.hazard_handled_or_scoped:
            return False
        if self.legacy_history_possible and not self.compatibility_disposition:
            return False
        return True


class CorrectTopologyHazardGate:
    name = "CorrectTopologyHazardGate"
    reads = (
        "topology_anchor_present",
        "future_hazard_inferred",
        "hard_gate_without_anchor",
        "required_route_created",
        "hazard_handled_or_scoped",
        "legacy_history_possible",
        "compatibility_disposition",
        "final_claim",
    )
    writes = reads
    accepted_input_type = TopologyHazardInput
    input_description = "topology hazard observation or confidence claim"
    output_description = "topology hazard review state"

    def apply(self, input_obj: TopologyHazardInput, state: TopologyHazardState) -> Iterable[FunctionResult]:
        action = input_obj.action_type
        if action == "observe_topology_anchor":
            yield FunctionResult(
                TopologyHazardOutput("anchor_observed"),
                replace(state, topology_anchor_present=True, final_claim="none"),
                label="anchor_observed",
            )
        elif action == "infer_future_hazard":
            if state.topology_anchor_present:
                yield FunctionResult(
                    TopologyHazardOutput("anchored_hazard_inferred"),
                    replace(state, future_hazard_inferred=True, final_claim="none"),
                    label="anchored_hazard_inferred",
                )
            else:
                yield FunctionResult(
                    TopologyHazardOutput("unanchored_observation_only"),
                    replace(state, final_claim="none"),
                    label="unanchored_observation_only",
                )
        elif action == "create_required_route":
            if state.future_hazard_inferred:
                yield FunctionResult(
                    TopologyHazardOutput("required_route_created"),
                    replace(state, required_route_created=True, final_claim="none"),
                    label="required_route_created",
                )
            else:
                yield FunctionResult(
                    TopologyHazardOutput("route_not_applicable"),
                    state,
                    label="route_not_applicable",
                )
        elif action == "handle_or_scope_hazard":
            if state.required_route_created:
                yield FunctionResult(
                    TopologyHazardOutput("hazard_handled_or_scoped"),
                    replace(state, hazard_handled_or_scoped=True, final_claim="none"),
                    label="hazard_handled_or_scoped",
                )
            else:
                yield FunctionResult(
                    TopologyHazardOutput("handle_not_applicable"),
                    state,
                    label="handle_not_applicable",
                )
        elif action == "observe_legacy_history":
            yield FunctionResult(
                TopologyHazardOutput("legacy_history_observed"),
                replace(state, legacy_history_possible=True, final_claim="none"),
                label="legacy_history_observed",
            )
        elif action == "choose_compatibility_disposition":
            if state.legacy_history_possible:
                yield FunctionResult(
                    TopologyHazardOutput("compatibility_disposition_chosen"),
                    replace(state, compatibility_disposition=True, final_claim="none"),
                    label="compatibility_disposition_chosen",
                )
            else:
                yield FunctionResult(
                    TopologyHazardOutput("compatibility_not_applicable"),
                    state,
                    label="compatibility_not_applicable",
                )
        elif action == "claim_full_confidence":
            if state.full_claim_allowed():
                yield FunctionResult(
                    TopologyHazardOutput("full_claim_accepted"),
                    replace(state, final_claim="full"),
                    label="full_claim_accepted",
                )
            else:
                yield FunctionResult(
                    TopologyHazardOutput("scoped_or_blocked_claim"),
                    replace(state, final_claim="scoped_or_blocked"),
                    label="scoped_or_blocked_claim",
                )


class BrokenUnanchoredHardGate(CorrectTopologyHazardGate):
    name = "BrokenUnanchoredHardGate"

    def apply(self, input_obj: TopologyHazardInput, state: TopologyHazardState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "infer_future_hazard" and not state.topology_anchor_present:
            yield FunctionResult(
                TopologyHazardOutput("unanchored_hard_gate"),
                replace(state, hard_gate_without_anchor=True, final_claim="blocked"),
                label="unanchored_hard_gate",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenFullWithoutRoute(CorrectTopologyHazardGate):
    name = "BrokenFullWithoutRoute"

    def apply(self, input_obj: TopologyHazardInput, state: TopologyHazardState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "claim_full_confidence":
            yield FunctionResult(
                TopologyHazardOutput("full_claim_accepted"),
                replace(state, final_claim="full"),
                label="full_claim_accepted",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenCompatibilityIgnored(CorrectTopologyHazardGate):
    name = "BrokenCompatibilityIgnored"

    def apply(self, input_obj: TopologyHazardInput, state: TopologyHazardState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "claim_full_confidence" and state.legacy_history_possible:
            yield FunctionResult(
                TopologyHazardOutput("full_claim_accepted"),
                replace(state, final_claim="full"),
                label="full_claim_accepted",
            )
            return
        yield from super().apply(input_obj, state)


def terminal_predicate(current_output, state, trace) -> bool:
    del state, trace
    return isinstance(current_output, TopologyHazardOutput) and current_output.status in {
        "full_claim_accepted",
        "scoped_or_blocked_claim",
        "unanchored_hard_gate",
    }


def unanchored_hazards_do_not_become_hard_gates(state: TopologyHazardState, trace) -> InvariantResult:
    del trace
    if state.hard_gate_without_anchor:
        return InvariantResult.fail("unanchored AI risk became a hard FlowGuard gate")
    return InvariantResult.pass_()


def anchored_hazards_need_route_or_scope(state: TopologyHazardState, trace) -> InvariantResult:
    del trace
    if state.future_hazard_inferred and state.final_claim == "full" and not state.hazard_handled_or_scoped:
        return InvariantResult.fail("full confidence accepted before anchored topology hazard was handled or scoped")
    return InvariantResult.pass_()


def compatibility_history_gets_disposition(state: TopologyHazardState, trace) -> InvariantResult:
    del trace
    if state.legacy_history_possible and state.final_claim == "full" and not state.compatibility_disposition:
        return InvariantResult.fail("full confidence accepted before legacy/history compatibility disposition")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "unanchored_hazards_do_not_become_hard_gates",
        "Unanchored AI risk observations cannot act as hard FlowGuard gates.",
        unanchored_hazards_do_not_become_hard_gates,
    ),
    Invariant(
        "anchored_hazards_need_route_or_scope",
        "Anchored topology hazards require route work, handling, or scoped confidence before full confidence.",
        anchored_hazards_need_route_or_scope,
    ),
    Invariant(
        "compatibility_history_gets_disposition",
        "Old-shape/history topology requires compatibility disposition before full confidence.",
        compatibility_history_gets_disposition,
    ),
)

EXTERNAL_INPUTS = (
    TopologyHazardInput("observe_topology_anchor"),
    TopologyHazardInput("infer_future_hazard"),
    TopologyHazardInput("create_required_route"),
    TopologyHazardInput("handle_or_scope_hazard"),
    TopologyHazardInput("observe_legacy_history"),
    TopologyHazardInput("choose_compatibility_disposition"),
    TopologyHazardInput("claim_full_confidence"),
)

MAX_SEQUENCE_LENGTH = 5


def initial_state() -> TopologyHazardState:
    return TopologyHazardState()


def build_correct_workflow() -> Workflow:
    return Workflow((CorrectTopologyHazardGate(),), name="topology_hazard_review_correct")


def build_broken_workflows() -> tuple[Workflow, ...]:
    return (
        Workflow((BrokenUnanchoredHardGate(),), name="topology_hazard_unanchored_hard_gate"),
        Workflow((BrokenFullWithoutRoute(),), name="topology_hazard_full_without_route"),
        Workflow((BrokenCompatibilityIgnored(),), name="topology_hazard_compatibility_ignored"),
    )


__all__ = [
    "EXTERNAL_INPUTS",
    "INVARIANTS",
    "MAX_SEQUENCE_LENGTH",
    "TopologyHazardInput",
    "TopologyHazardOutput",
    "TopologyHazardState",
    "build_broken_workflows",
    "build_correct_workflow",
    "initial_state",
    "terminal_predicate",
]


from flowguard.skill_contract_model import (
    FLOWGUARD_MODEL_MARKER,
    build_skill_contract_model_export,
)


def export_contract_model():
    """Project the existing topology-hazard owner for SkillGuard V2."""

    return build_skill_contract_model_export(
        skill_id="flowguard-model-topology-hazard-review",
        route_id="model_topology_hazard_review",
        owner_id="model_topology_hazard_review",
        parent_model_id="flowguard.model_first_function_flow",
        business_intent="Review topology-anchored future-use hazards without converting unanchored concerns into hard gates.",
        claim_boundary="Projection only; usage anchors, dispositions, compatibility effects, and native hazard checks remain authoritative.",
    )


__all__ = [*__all__, "FLOWGUARD_MODEL_MARKER", "export_contract_model"]
