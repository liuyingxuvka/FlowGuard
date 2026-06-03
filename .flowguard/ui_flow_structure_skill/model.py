"""FlowGuard Risk Purpose Header.

Created with FlowGuard:
https://github.com/liuyingxuvka/FlowGuard

Purpose:
Models the UI flow structure satellite rollout before implementation. The
model checks that the new route first creates/reviews a UI interaction model
and app-level journey coverage before deriving UI structure.

Guards against:
- treating UI flow structure as direct model-to-layout prose;
- publishing the skill without a checked UI interaction model stage;
- claiming route completion without structure derivation evidence;
- accepting a structure derivation that lacks parent/child UI topology.
- accepting a UI structure route that never reviewed duplicate information or
  overlapping same-level controls.
- accepting a complete-app UI release that never reviewed launch-to-terminal
  journey coverage.
- accepting complete-app UI coverage while visible/enabled controls or modeled
  events remain outside every journey, terminal allowance, or blindspot.
- accepting an implemented/runnable UI completion claim without aligning the
  feature model, UI journey model, and real browser/manual click-through
  evidence.
- accepting UI text hierarchy evidence without soft visual typography handoff
  guidance for reusable text treatments and intentional exceptions.

Use before editing:
UI flow structure helper APIs, satellite skill wording, templates, docs, and
release routing.

Run:
python .flowguard/ui_flow_structure_skill/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


@dataclass(frozen=True)
class RolloutAction:
    action_type: str


@dataclass(frozen=True)
class RolloutOutput:
    status: str


@dataclass(frozen=True)
class RolloutState:
    ui_model_created: bool = False
    ui_model_reviewed: bool = False
    journey_coverage_reviewed: bool = False
    launch_entry_inventory_present: bool = False
    terminal_recovery_paths_reviewed: bool = False
    visible_control_branches_reviewed: bool = False
    feature_contracts_aligned: bool = False
    structure_derived: bool = False
    parent_child_topology_present: bool = False
    redundancy_reviewed: bool = False
    text_hierarchy_reviewed: bool = False
    typography_handoff_guidance_reviewed: bool = False
    implementation_validation_reviewed: bool = False
    clickthrough_evidence_reviewed: bool = False
    implementation_evidence_fresh: bool = False
    skill_documented: bool = False
    release_claim: str = "none"
    implemented_ui_claim: str = "none"


class CorrectUiFlowStructureRollout:
    name = "CorrectUiFlowStructureRollout"
    reads = (
        "ui_model_created",
        "ui_model_reviewed",
        "journey_coverage_reviewed",
        "launch_entry_inventory_present",
        "terminal_recovery_paths_reviewed",
        "visible_control_branches_reviewed",
        "feature_contracts_aligned",
        "structure_derived",
        "parent_child_topology_present",
        "redundancy_reviewed",
        "text_hierarchy_reviewed",
        "typography_handoff_guidance_reviewed",
        "implementation_validation_reviewed",
        "clickthrough_evidence_reviewed",
        "implementation_evidence_fresh",
        "skill_documented",
        "release_claim",
        "implemented_ui_claim",
    )
    writes = reads
    accepted_input_type = RolloutAction
    input_description = "UI flow structure rollout action"
    output_description = "rollout stage result"
    idempotency = "same stage keeps the rollout evidence stable"

    def apply(self, input_obj: RolloutAction, state: RolloutState) -> Iterable[FunctionResult]:
        action = input_obj.action_type
        if action == "create_ui_model":
            yield FunctionResult(
                RolloutOutput("ui_model_created"),
                replace(state, ui_model_created=True),
                label="ui_model_created",
            )
            return
        if action == "review_ui_model":
            if not state.ui_model_created:
                yield FunctionResult(
                    RolloutOutput("ui_model_review_rejected"),
                    state,
                    label="ui_model_review_rejected",
                )
                return
            yield FunctionResult(
                RolloutOutput("ui_model_reviewed"),
                replace(state, ui_model_reviewed=True),
                label="ui_model_reviewed",
            )
            return
        if action == "review_journey_coverage":
            if not state.ui_model_reviewed:
                yield FunctionResult(
                    RolloutOutput("journey_coverage_rejected"),
                    state,
                    label="journey_coverage_rejected",
                )
                return
            yield FunctionResult(
                RolloutOutput("journey_coverage_reviewed"),
                replace(
                    state,
                    journey_coverage_reviewed=True,
                    launch_entry_inventory_present=True,
                    terminal_recovery_paths_reviewed=True,
                    visible_control_branches_reviewed=True,
                ),
                label="journey_coverage_reviewed",
            )
            return
        if action == "derive_structure":
            if not state.ui_model_reviewed or not state.journey_coverage_reviewed:
                yield FunctionResult(
                    RolloutOutput("structure_derivation_rejected"),
                    state,
                    label="structure_derivation_rejected",
                )
                return
            yield FunctionResult(
                RolloutOutput("structure_derived"),
                replace(
                    state,
                    structure_derived=True,
                    parent_child_topology_present=True,
                    redundancy_reviewed=True,
                    text_hierarchy_reviewed=True,
                    typography_handoff_guidance_reviewed=True,
                ),
                label="structure_derived",
            )
            return
        if action == "review_implementation_validation":
            if not (
                state.ui_model_reviewed
                and state.journey_coverage_reviewed
                and state.structure_derived
                and state.text_hierarchy_reviewed
                and state.typography_handoff_guidance_reviewed
            ):
                yield FunctionResult(
                    RolloutOutput("implementation_validation_rejected"),
                    state,
                    label="implementation_validation_rejected",
                )
                return
            yield FunctionResult(
                RolloutOutput("implementation_validation_reviewed"),
                replace(
                    state,
                    feature_contracts_aligned=True,
                    implementation_validation_reviewed=True,
                    clickthrough_evidence_reviewed=True,
                    implementation_evidence_fresh=True,
                ),
                label="implementation_validation_reviewed",
            )
            return
        if action == "document_skill":
            if not state.structure_derived:
                yield FunctionResult(
                    RolloutOutput("skill_documentation_rejected"),
                    state,
                    label="skill_documentation_rejected",
                )
                return
            yield FunctionResult(
                RolloutOutput("skill_documented"),
                replace(state, skill_documented=True),
                label="skill_documented",
            )
            return
        if action == "claim_release":
            accepted = (
                state.ui_model_reviewed
                and state.journey_coverage_reviewed
                and state.launch_entry_inventory_present
                and state.terminal_recovery_paths_reviewed
                and state.visible_control_branches_reviewed
                and state.structure_derived
                and state.parent_child_topology_present
                and state.redundancy_reviewed
                and state.text_hierarchy_reviewed
                and state.typography_handoff_guidance_reviewed
                and state.skill_documented
            )
            yield FunctionResult(
                RolloutOutput("release_accepted" if accepted else "release_rejected"),
                replace(state, release_claim="accepted" if accepted else "rejected"),
                label="release_accepted" if accepted else "release_rejected",
            )
            return
        if action == "claim_implemented_ui":
            accepted = (
                state.skill_documented
                and state.feature_contracts_aligned
                and state.implementation_validation_reviewed
                and state.clickthrough_evidence_reviewed
                and state.implementation_evidence_fresh
            )
            yield FunctionResult(
                RolloutOutput("implemented_ui_accepted" if accepted else "implemented_ui_rejected"),
                replace(state, implemented_ui_claim="accepted" if accepted else "rejected"),
                label="implemented_ui_accepted" if accepted else "implemented_ui_rejected",
            )


class BrokenLayoutOnlyRollout(CorrectUiFlowStructureRollout):
    name = "BrokenLayoutOnlyRollout"
    idempotency = "Broken variant derives layout without a checked UI interaction model."

    def apply(self, input_obj: RolloutAction, state: RolloutState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "derive_structure":
            yield FunctionResult(
                RolloutOutput("structure_derived"),
                replace(
                    state,
                    structure_derived=True,
                    parent_child_topology_present=True,
                ),
                label="structure_derived",
            )
            return
        if input_obj.action_type == "claim_release":
            accepted = state.structure_derived and state.parent_child_topology_present
            yield FunctionResult(
                RolloutOutput("release_accepted" if accepted else "release_rejected"),
                replace(state, release_claim="accepted" if accepted else "rejected"),
                label="release_accepted" if accepted else "release_rejected",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenNoTopologyRollout(CorrectUiFlowStructureRollout):
    name = "BrokenNoTopologyRollout"
    idempotency = "Broken variant reviews the model but derives no parent/child topology."

    def apply(self, input_obj: RolloutAction, state: RolloutState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "derive_structure":
            if not state.ui_model_reviewed:
                yield FunctionResult(
                    RolloutOutput("structure_derivation_rejected"),
                    state,
                    label="structure_derivation_rejected",
                )
                return
            yield FunctionResult(
                RolloutOutput("structure_derived_without_topology"),
                replace(state, structure_derived=True, parent_child_topology_present=False),
                label="structure_derived_without_topology",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenNoJourneyCoverageRollout(CorrectUiFlowStructureRollout):
    name = "BrokenNoJourneyCoverageRollout"
    idempotency = "Broken variant derives structure and accepts release without app-level journey coverage."

    def apply(self, input_obj: RolloutAction, state: RolloutState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "derive_structure":
            if not state.ui_model_reviewed:
                yield FunctionResult(
                    RolloutOutput("structure_derivation_rejected"),
                    state,
                    label="structure_derivation_rejected",
                )
                return
            yield FunctionResult(
                RolloutOutput("structure_derived"),
                replace(
                    state,
                    structure_derived=True,
                    parent_child_topology_present=True,
                    redundancy_reviewed=True,
                ),
                label="structure_derived",
            )
            return
        if input_obj.action_type == "claim_release":
            accepted = (
                state.ui_model_reviewed
                and state.structure_derived
                and state.parent_child_topology_present
                and state.redundancy_reviewed
                and state.skill_documented
            )
            yield FunctionResult(
                RolloutOutput("release_accepted" if accepted else "release_rejected"),
                replace(state, release_claim="accepted" if accepted else "rejected"),
                label="release_accepted" if accepted else "release_rejected",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenNoVisibleBranchCoverageRollout(CorrectUiFlowStructureRollout):
    name = "BrokenNoVisibleBranchCoverageRollout"
    idempotency = "Broken variant accepts journey coverage without checking every visible control branch."

    def apply(self, input_obj: RolloutAction, state: RolloutState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "review_journey_coverage":
            if not state.ui_model_reviewed:
                yield FunctionResult(
                    RolloutOutput("journey_coverage_rejected"),
                    state,
                    label="journey_coverage_rejected",
                )
                return
            yield FunctionResult(
                RolloutOutput("journey_coverage_reviewed"),
                replace(
                    state,
                    journey_coverage_reviewed=True,
                    launch_entry_inventory_present=True,
                    terminal_recovery_paths_reviewed=True,
                    visible_control_branches_reviewed=False,
                ),
                label="journey_coverage_reviewed_without_visible_branch_review",
            )
            return
        if input_obj.action_type == "claim_release":
            accepted = (
                state.ui_model_reviewed
                and state.journey_coverage_reviewed
                and state.launch_entry_inventory_present
                and state.terminal_recovery_paths_reviewed
                and state.structure_derived
                and state.parent_child_topology_present
                and state.redundancy_reviewed
                and state.skill_documented
            )
            yield FunctionResult(
                RolloutOutput("release_accepted" if accepted else "release_rejected"),
                replace(state, release_claim="accepted" if accepted else "rejected"),
                label="release_accepted" if accepted else "release_rejected",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenNoTypographyHandoffRollout(CorrectUiFlowStructureRollout):
    name = "BrokenNoTypographyHandoffRollout"
    idempotency = "Broken variant accepts text hierarchy without visual typography handoff guidance."

    def apply(self, input_obj: RolloutAction, state: RolloutState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "derive_structure":
            if not state.ui_model_reviewed or not state.journey_coverage_reviewed:
                yield FunctionResult(
                    RolloutOutput("structure_derivation_rejected"),
                    state,
                    label="structure_derivation_rejected",
                )
                return
            yield FunctionResult(
                RolloutOutput("structure_derived"),
                replace(
                    state,
                    structure_derived=True,
                    parent_child_topology_present=True,
                    redundancy_reviewed=True,
                    text_hierarchy_reviewed=True,
                    typography_handoff_guidance_reviewed=False,
                ),
                label="structure_derived_without_typography_handoff",
            )
            return
        if input_obj.action_type == "claim_release":
            accepted = (
                state.ui_model_reviewed
                and state.journey_coverage_reviewed
                and state.launch_entry_inventory_present
                and state.terminal_recovery_paths_reviewed
                and state.visible_control_branches_reviewed
                and state.structure_derived
                and state.parent_child_topology_present
                and state.redundancy_reviewed
                and state.text_hierarchy_reviewed
                and state.skill_documented
            )
            yield FunctionResult(
                RolloutOutput("release_accepted" if accepted else "release_rejected"),
                replace(state, release_claim="accepted" if accepted else "rejected"),
                label="release_accepted" if accepted else "release_rejected",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenImplementationWithoutFeatureAlignmentRollout(CorrectUiFlowStructureRollout):
    name = "BrokenImplementationWithoutFeatureAlignmentRollout"
    idempotency = "Broken variant accepts implementation validation without functional feature alignment."

    def apply(self, input_obj: RolloutAction, state: RolloutState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "review_implementation_validation":
            if not state.structure_derived:
                yield FunctionResult(
                    RolloutOutput("implementation_validation_rejected"),
                    state,
                    label="implementation_validation_rejected",
                )
                return
            yield FunctionResult(
                RolloutOutput("implementation_validation_reviewed"),
                replace(
                    state,
                    feature_contracts_aligned=False,
                    implementation_validation_reviewed=True,
                    clickthrough_evidence_reviewed=True,
                    implementation_evidence_fresh=True,
                ),
                label="implementation_validation_reviewed_without_feature_alignment",
            )
            return
        if input_obj.action_type == "claim_implemented_ui":
            accepted = (
                state.skill_documented
                and state.implementation_validation_reviewed
                and state.clickthrough_evidence_reviewed
                and state.implementation_evidence_fresh
            )
            yield FunctionResult(
                RolloutOutput("implemented_ui_accepted" if accepted else "implemented_ui_rejected"),
                replace(state, implemented_ui_claim="accepted" if accepted else "rejected"),
                label="implemented_ui_accepted" if accepted else "implemented_ui_rejected",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenImplementationWithoutClickthroughRollout(CorrectUiFlowStructureRollout):
    name = "BrokenImplementationWithoutClickthroughRollout"
    idempotency = "Broken variant accepts implementation validation without real UI click-through evidence."

    def apply(self, input_obj: RolloutAction, state: RolloutState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "review_implementation_validation":
            if not state.structure_derived:
                yield FunctionResult(
                    RolloutOutput("implementation_validation_rejected"),
                    state,
                    label="implementation_validation_rejected",
                )
                return
            yield FunctionResult(
                RolloutOutput("implementation_validation_reviewed"),
                replace(
                    state,
                    feature_contracts_aligned=True,
                    implementation_validation_reviewed=True,
                    clickthrough_evidence_reviewed=False,
                    implementation_evidence_fresh=True,
                ),
                label="implementation_validation_reviewed_without_clickthrough",
            )
            return
        if input_obj.action_type == "claim_implemented_ui":
            accepted = (
                state.skill_documented
                and state.feature_contracts_aligned
                and state.implementation_validation_reviewed
                and state.implementation_evidence_fresh
            )
            yield FunctionResult(
                RolloutOutput("implemented_ui_accepted" if accepted else "implemented_ui_rejected"),
                replace(state, implemented_ui_claim="accepted" if accepted else "rejected"),
                label="implemented_ui_accepted" if accepted else "implemented_ui_rejected",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenStaleImplementationEvidenceRollout(CorrectUiFlowStructureRollout):
    name = "BrokenStaleImplementationEvidenceRollout"
    idempotency = "Broken variant accepts implementation validation with stale or ungrounded evidence."

    def apply(self, input_obj: RolloutAction, state: RolloutState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "review_implementation_validation":
            if not state.structure_derived:
                yield FunctionResult(
                    RolloutOutput("implementation_validation_rejected"),
                    state,
                    label="implementation_validation_rejected",
                )
                return
            yield FunctionResult(
                RolloutOutput("implementation_validation_reviewed"),
                replace(
                    state,
                    feature_contracts_aligned=True,
                    implementation_validation_reviewed=True,
                    clickthrough_evidence_reviewed=True,
                    implementation_evidence_fresh=False,
                ),
                label="implementation_validation_reviewed_with_stale_evidence",
            )
            return
        if input_obj.action_type == "claim_implemented_ui":
            accepted = (
                state.skill_documented
                and state.feature_contracts_aligned
                and state.implementation_validation_reviewed
                and state.clickthrough_evidence_reviewed
            )
            yield FunctionResult(
                RolloutOutput("implemented_ui_accepted" if accepted else "implemented_ui_rejected"),
                replace(state, implemented_ui_claim="accepted" if accepted else "rejected"),
                label="implemented_ui_accepted" if accepted else "implemented_ui_rejected",
            )
            return
        yield from super().apply(input_obj, state)


def terminal_predicate(current_output, state, trace) -> bool:
    del state, trace
    return isinstance(current_output, RolloutOutput) and (
        current_output.status.startswith("release_")
        or current_output.status.startswith("implemented_ui_")
    )


def release_requires_reviewed_ui_model(state: RolloutState, trace) -> InvariantResult:
    del trace
    if state.release_claim == "accepted" and not state.ui_model_reviewed:
        return InvariantResult.fail("release accepted without reviewed UI interaction model")
    return InvariantResult.pass_()


def release_requires_derived_topology(state: RolloutState, trace) -> InvariantResult:
    del trace
    if state.release_claim == "accepted" and not state.parent_child_topology_present:
        return InvariantResult.fail("release accepted without parent/child UI topology")
    return InvariantResult.pass_()


def release_requires_journey_coverage(state: RolloutState, trace) -> InvariantResult:
    del trace
    if state.release_claim == "accepted" and not (
        state.journey_coverage_reviewed
        and state.launch_entry_inventory_present
        and state.terminal_recovery_paths_reviewed
        and state.visible_control_branches_reviewed
    ):
        return InvariantResult.fail("release accepted without exhaustive launch-to-terminal UI journey coverage")
    return InvariantResult.pass_()


def release_requires_redundancy_review(state: RolloutState, trace) -> InvariantResult:
    del trace
    if state.release_claim == "accepted" and not state.redundancy_reviewed:
        return InvariantResult.fail("release accepted without duplicate information/control review")
    return InvariantResult.pass_()


def release_requires_typography_handoff_guidance(state: RolloutState, trace) -> InvariantResult:
    del trace
    if state.release_claim == "accepted" and not state.typography_handoff_guidance_reviewed:
        return InvariantResult.fail("release accepted without soft visual typography handoff guidance")
    return InvariantResult.pass_()


def implemented_ui_requires_typography_handoff_guidance(state: RolloutState, trace) -> InvariantResult:
    del trace
    if state.implemented_ui_claim == "accepted" and not state.typography_handoff_guidance_reviewed:
        return InvariantResult.fail("implemented UI accepted without soft visual typography handoff guidance")
    return InvariantResult.pass_()


def implemented_ui_requires_feature_alignment(state: RolloutState, trace) -> InvariantResult:
    del trace
    if state.implemented_ui_claim == "accepted" and not state.feature_contracts_aligned:
        return InvariantResult.fail("implemented UI accepted without feature/UI model alignment")
    return InvariantResult.pass_()


def implemented_ui_requires_clickthrough_evidence(state: RolloutState, trace) -> InvariantResult:
    del trace
    if state.implemented_ui_claim == "accepted" and not state.clickthrough_evidence_reviewed:
        return InvariantResult.fail("implemented UI accepted without browser/manual click-through evidence")
    return InvariantResult.pass_()


def implemented_ui_requires_fresh_evidence(state: RolloutState, trace) -> InvariantResult:
    del trace
    if state.implemented_ui_claim == "accepted" and not state.implementation_evidence_fresh:
        return InvariantResult.fail("implemented UI accepted with stale or ungrounded evidence")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "release_requires_reviewed_ui_model",
        "UI flow structure release claims require a reviewed UI interaction model.",
        release_requires_reviewed_ui_model,
    ),
    Invariant(
        "release_requires_derived_topology",
        "UI flow structure release claims require derived parent/child UI topology.",
        release_requires_derived_topology,
    ),
    Invariant(
        "release_requires_journey_coverage",
        "Complete app-level UI release claims require launch-to-terminal journey coverage.",
        release_requires_journey_coverage,
    ),
    Invariant(
        "release_requires_redundancy_review",
        "UI flow structure release claims require duplicate information/control review.",
        release_requires_redundancy_review,
    ),
    Invariant(
        "release_requires_typography_handoff_guidance",
        "UI flow structure release claims require soft visual typography handoff guidance.",
        release_requires_typography_handoff_guidance,
    ),
    Invariant(
        "implemented_ui_requires_typography_handoff_guidance",
        "Implemented UI claims require soft visual typography handoff guidance.",
        implemented_ui_requires_typography_handoff_guidance,
    ),
    Invariant(
        "implemented_ui_requires_feature_alignment",
        "Implemented UI claims require functional feature contracts to align with UI journeys.",
        implemented_ui_requires_feature_alignment,
    ),
    Invariant(
        "implemented_ui_requires_clickthrough_evidence",
        "Implemented UI claims require real browser/manual click-through evidence.",
        implemented_ui_requires_clickthrough_evidence,
    ),
    Invariant(
        "implemented_ui_requires_fresh_evidence",
        "Implemented UI claims require current implementation evidence.",
        implemented_ui_requires_fresh_evidence,
    ),
)

EXTERNAL_INPUTS = (
    RolloutAction("create_ui_model"),
    RolloutAction("review_ui_model"),
    RolloutAction("review_journey_coverage"),
    RolloutAction("derive_structure"),
    RolloutAction("review_implementation_validation"),
    RolloutAction("document_skill"),
    RolloutAction("claim_implemented_ui"),
    RolloutAction("claim_release"),
)

RELEASE_INPUTS = (
    RolloutAction("create_ui_model"),
    RolloutAction("review_ui_model"),
    RolloutAction("review_journey_coverage"),
    RolloutAction("derive_structure"),
    RolloutAction("document_skill"),
    RolloutAction("claim_release"),
)

IMPLEMENTATION_INPUTS = (
    RolloutAction("create_ui_model"),
    RolloutAction("review_ui_model"),
    RolloutAction("review_journey_coverage"),
    RolloutAction("derive_structure"),
    RolloutAction("review_implementation_validation"),
    RolloutAction("document_skill"),
    RolloutAction("claim_implemented_ui"),
)

MAX_SEQUENCE_LENGTH = 7


def initial_state() -> RolloutState:
    return RolloutState()


def build_correct_workflow() -> Workflow:
    return Workflow((CorrectUiFlowStructureRollout(),), name="ui_flow_structure_correct")


def build_broken_layout_only_workflow() -> Workflow:
    return Workflow((BrokenLayoutOnlyRollout(),), name="ui_flow_structure_layout_only_broken")


def build_broken_no_topology_workflow() -> Workflow:
    return Workflow((BrokenNoTopologyRollout(),), name="ui_flow_structure_no_topology_broken")


def build_broken_no_journey_coverage_workflow() -> Workflow:
    return Workflow((BrokenNoJourneyCoverageRollout(),), name="ui_flow_structure_no_journey_coverage_broken")


def build_broken_no_visible_branch_coverage_workflow() -> Workflow:
    return Workflow((BrokenNoVisibleBranchCoverageRollout(),), name="ui_flow_structure_no_visible_branch_coverage_broken")


def build_broken_no_typography_handoff_workflow() -> Workflow:
    return Workflow((BrokenNoTypographyHandoffRollout(),), name="ui_flow_structure_no_typography_handoff_broken")


def build_broken_implementation_without_feature_alignment_workflow() -> Workflow:
    return Workflow(
        (BrokenImplementationWithoutFeatureAlignmentRollout(),),
        name="ui_flow_structure_implementation_without_feature_alignment_broken",
    )


def build_broken_implementation_without_clickthrough_workflow() -> Workflow:
    return Workflow(
        (BrokenImplementationWithoutClickthroughRollout(),),
        name="ui_flow_structure_implementation_without_clickthrough_broken",
    )


def build_broken_stale_implementation_evidence_workflow() -> Workflow:
    return Workflow(
        (BrokenStaleImplementationEvidenceRollout(),),
        name="ui_flow_structure_stale_implementation_evidence_broken",
    )


__all__ = [
    "EXTERNAL_INPUTS",
    "IMPLEMENTATION_INPUTS",
    "INVARIANTS",
    "MAX_SEQUENCE_LENGTH",
    "RELEASE_INPUTS",
    "RolloutAction",
    "RolloutOutput",
    "RolloutState",
    "build_broken_layout_only_workflow",
    "build_broken_implementation_without_clickthrough_workflow",
    "build_broken_implementation_without_feature_alignment_workflow",
    "build_broken_no_journey_coverage_workflow",
    "build_broken_no_typography_handoff_workflow",
    "build_broken_no_visible_branch_coverage_workflow",
    "build_broken_no_topology_workflow",
    "build_broken_stale_implementation_evidence_workflow",
    "build_correct_workflow",
    "initial_state",
    "terminal_predicate",
]
