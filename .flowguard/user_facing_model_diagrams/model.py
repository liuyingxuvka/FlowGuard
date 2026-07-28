"""FlowGuard model for lightweight user-facing diagram prompt guidance.

Purpose:
Model the prompt upgrade before editing skill text. The desired behavior is a
lightweight rule: diagrams are optional and judgment-based, but when they are
used they should be expressive enough to explain model value.

Guards against:
- turning diagrams into a mandatory output for every FlowGuard task;
- accepting shallow diagrams that do not show branches, gates, evidence, or
  claim boundaries;
- accepting diagrams without a short current-situation note for non-trivial
  work;
- claiming the rollout is complete before the kernel and selected high-value
  satellite skills are covered.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


@dataclass(frozen=True)
class PromptAction:
    action_type: str


@dataclass(frozen=True)
class PromptOutput:
    status: str


@dataclass(frozen=True)
class PromptState:
    kernel_guidance: bool = False
    ui_guidance: bool = False
    mesh_guidance: bool = False
    process_guidance: bool = False
    optional_rule: bool = False
    no_trivial_force: bool = False
    expressive_diagram_guidance: bool = False
    current_situation_guidance: bool = False
    release_claim: str = "none"

    def selected_routes_covered(self) -> bool:
        return self.kernel_guidance and self.ui_guidance and self.mesh_guidance and self.process_guidance

    def lightweight_rule_present(self) -> bool:
        return self.optional_rule and self.no_trivial_force and self.current_situation_guidance


class CorrectPromptRollout:
    name = "CorrectPromptRollout"
    reads = (
        "kernel_guidance",
        "ui_guidance",
        "mesh_guidance",
        "process_guidance",
        "optional_rule",
        "no_trivial_force",
        "expressive_diagram_guidance",
        "current_situation_guidance",
        "release_claim",
    )
    writes = reads
    accepted_input_type = PromptAction
    input_description = "prompt guidance rollout action"
    output_description = "prompt guidance state update or release claim"
    idempotency = "Repeated prompt updates keep the same guidance flags."

    def apply(self, input_obj: PromptAction, state: PromptState) -> Iterable[FunctionResult]:
        action = input_obj.action_type
        if action == "add_kernel_guidance":
            yield FunctionResult(
                PromptOutput("kernel_guidance_added"),
                replace(
                    state,
                    kernel_guidance=True,
                    optional_rule=True,
                    no_trivial_force=True,
                    current_situation_guidance=True,
                ),
                label="kernel_guidance_added",
                reason="shared rule adds current situation notes and keeps diagrams optional",
            )
            return
        if action == "add_ui_guidance":
            yield FunctionResult(
                PromptOutput("ui_guidance_added"),
                replace(state, ui_guidance=True),
                label="ui_guidance_added",
                reason="UI route names launch entries, controls, failures, recovery, and evidence",
            )
            return
        if action == "add_mesh_guidance":
            yield FunctionResult(
                PromptOutput("mesh_guidance_added"),
                replace(state, mesh_guidance=True),
                label="mesh_guidance_added",
                reason="ModelMesh route names parent/child boundaries and reattachment evidence",
            )
            return
        if action == "add_process_guidance":
            yield FunctionResult(
                PromptOutput("process_guidance_added"),
                replace(state, process_guidance=True),
                label="process_guidance_added",
                reason="DevelopmentProcessFlow route names lifecycle stages and validation evidence",
            )
            return
        if action == "add_expressive_diagram_guidance":
            yield FunctionResult(
                PromptOutput("expressive_diagram_guidance_added"),
                replace(state, expressive_diagram_guidance=True),
                label="expressive_diagram_guidance_added",
                reason="when diagrams are used they should show branches, gates, evidence, and claim limits",
            )
            return
        if action == "claim_release":
            accepted = (
                state.selected_routes_covered()
                and state.lightweight_rule_present()
                and state.expressive_diagram_guidance
            )
            yield FunctionResult(
                PromptOutput("release_accepted" if accepted else "release_rejected"),
                replace(state, release_claim="accepted" if accepted else "rejected"),
                label="release_accepted" if accepted else "release_rejected",
                reason="release claim depends on current situation notes, lightweight rule, expressive diagrams, and selected route coverage",
            )


class BrokenMandatoryDiagramRollout(CorrectPromptRollout):
    name = "BrokenMandatoryDiagramRollout"
    idempotency = "Broken: makes diagrams mandatory for every task and still accepts release."

    def apply(self, input_obj: PromptAction, state: PromptState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "add_kernel_guidance":
            yield FunctionResult(
                PromptOutput("kernel_guidance_added"),
                replace(state, kernel_guidance=True, optional_rule=False, no_trivial_force=False),
                label="kernel_guidance_added_mandatory_everywhere",
                reason="broken prompt forces diagrams even for tiny or obvious tasks",
            )
            return
        if input_obj.action_type == "claim_release":
            accepted = (
                state.selected_routes_covered()
                and state.expressive_diagram_guidance
            )
            yield FunctionResult(
                PromptOutput("release_accepted" if accepted else "release_rejected"),
                replace(state, release_claim="accepted" if accepted else "rejected"),
                label="release_accepted" if accepted else "release_rejected",
                reason="broken rollout ignores the optional/no-trivial-force rule",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenShallowDiagramRollout(CorrectPromptRollout):
    name = "BrokenShallowDiagramRollout"
    idempotency = "Broken: accepts a prompt that only asks for shallow diagrams."

    def apply(self, input_obj: PromptAction, state: PromptState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "add_expressive_diagram_guidance":
            yield FunctionResult(
                PromptOutput("shallow_diagram_guidance_added"),
                state,
                label="shallow_diagram_guidance_added",
                reason="broken prompt does not ask diagrams to show branches, gates, evidence, or claim boundaries",
            )
            return
        if input_obj.action_type == "claim_release":
            accepted = state.selected_routes_covered() and state.lightweight_rule_present()
            yield FunctionResult(
                PromptOutput("release_accepted" if accepted else "release_rejected"),
                replace(state, release_claim="accepted" if accepted else "rejected"),
                label="release_accepted" if accepted else "release_rejected",
                reason="broken rollout ignores expressive diagram content",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenMissingRouteRollout(CorrectPromptRollout):
    name = "BrokenMissingRouteRollout"
    idempotency = "Broken: accepts rollout without all selected satellite routes."

    def apply(self, input_obj: PromptAction, state: PromptState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "claim_release":
            accepted = (
                state.kernel_guidance
                and state.ui_guidance
                and state.lightweight_rule_present()
                and state.expressive_diagram_guidance
            )
            yield FunctionResult(
                PromptOutput("release_accepted" if accepted else "release_rejected"),
                replace(state, release_claim="accepted" if accepted else "rejected"),
                label="release_accepted" if accepted else "release_rejected",
                reason="broken rollout ignores ModelMesh and DevelopmentProcessFlow route coverage",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenMissingCurrentSituationRollout(CorrectPromptRollout):
    name = "BrokenMissingCurrentSituationRollout"
    idempotency = "Broken: accepts rollout with diagrams but no current-situation note."

    def apply(self, input_obj: PromptAction, state: PromptState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "add_kernel_guidance":
            yield FunctionResult(
                PromptOutput("kernel_guidance_added"),
                replace(state, kernel_guidance=True, optional_rule=True, no_trivial_force=True),
                label="kernel_guidance_added_without_current_situation",
                reason="broken prompt adds diagram guidance without saying what FlowGuard is checking now",
            )
            return
        if input_obj.action_type == "claim_release":
            accepted = (
                state.selected_routes_covered()
                and state.optional_rule
                and state.no_trivial_force
                and state.expressive_diagram_guidance
            )
            yield FunctionResult(
                PromptOutput("release_accepted" if accepted else "release_rejected"),
                replace(state, release_claim="accepted" if accepted else "rejected"),
                label="release_accepted" if accepted else "release_rejected",
                reason="broken rollout ignores current-situation guidance",
            )
            return
        yield from super().apply(input_obj, state)


def release_requires_lightweight_rule(state: PromptState, trace) -> InvariantResult:
    del trace
    if state.release_claim == "accepted" and not state.lightweight_rule_present():
        return InvariantResult.fail("release accepted even though diagrams became mandatory or overbroad")
    return InvariantResult.pass_()


def release_requires_current_situation_guidance(state: PromptState, trace) -> InvariantResult:
    del trace
    if state.release_claim == "accepted" and not state.current_situation_guidance:
        return InvariantResult.fail("release accepted without current-situation guidance")
    return InvariantResult.pass_()


def release_requires_expressive_diagram_guidance(state: PromptState, trace) -> InvariantResult:
    del trace
    if state.release_claim == "accepted" and not state.expressive_diagram_guidance:
        return InvariantResult.fail("release accepted without expressive diagram guidance")
    return InvariantResult.pass_()


def release_requires_selected_route_coverage(state: PromptState, trace) -> InvariantResult:
    del trace
    if state.release_claim == "accepted" and not state.selected_routes_covered():
        return InvariantResult.fail("release accepted without all selected route guidance")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "release_requires_lightweight_rule",
        "Diagram guidance must remain optional, current, and not forced for trivial tasks.",
        release_requires_lightweight_rule,
    ),
    Invariant(
        "release_requires_current_situation_guidance",
        "Non-trivial diagram guidance needs a current-situation note.",
        release_requires_current_situation_guidance,
    ),
    Invariant(
        "release_requires_expressive_diagram_guidance",
        "When diagrams are used they must be encouraged to show branches, gates, evidence, and claim limits.",
        release_requires_expressive_diagram_guidance,
    ),
    Invariant(
        "release_requires_selected_route_coverage",
        "The rollout must cover the kernel plus UI, ModelMesh, and DevelopmentProcessFlow.",
        release_requires_selected_route_coverage,
    ),
)

EXTERNAL_INPUTS = (
    PromptAction("add_kernel_guidance"),
    PromptAction("add_ui_guidance"),
    PromptAction("add_mesh_guidance"),
    PromptAction("add_process_guidance"),
    PromptAction("add_expressive_diagram_guidance"),
    PromptAction("claim_release"),
)

MAX_SEQUENCE_LENGTH = 6


def initial_state() -> PromptState:
    return PromptState()


def build_correct_workflow() -> Workflow:
    return Workflow((CorrectPromptRollout(),), name="user_facing_model_diagrams_correct")


def build_broken_mandatory_workflow() -> Workflow:
    return Workflow((BrokenMandatoryDiagramRollout(),), name="user_facing_model_diagrams_mandatory")


def build_broken_shallow_workflow() -> Workflow:
    return Workflow((BrokenShallowDiagramRollout(),), name="user_facing_model_diagrams_shallow")


def build_broken_missing_route_workflow() -> Workflow:
    return Workflow((BrokenMissingRouteRollout(),), name="user_facing_model_diagrams_missing_route")


def build_broken_missing_current_situation_workflow() -> Workflow:
    return Workflow((BrokenMissingCurrentSituationRollout(),), name="user_facing_model_diagrams_missing_current")


__all__ = [
    "EXTERNAL_INPUTS",
    "INVARIANTS",
    "MAX_SEQUENCE_LENGTH",
    "PromptAction",
    "PromptOutput",
    "PromptState",
    "build_broken_mandatory_workflow",
    "build_broken_missing_current_situation_workflow",
    "build_broken_missing_route_workflow",
    "build_broken_shallow_workflow",
    "build_correct_workflow",
    "initial_state",
]
