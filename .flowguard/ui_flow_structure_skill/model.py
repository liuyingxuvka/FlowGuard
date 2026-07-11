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
- accepting display, text, visible-surface, or observed-surface modeling before
  every in-scope content candidate has one supported visibility decision.
- accepting internal content on an ordinary UI surface because it has a
  display owner, purpose, or free-text rationale.
- accepting user-on-demand content that is visible by default, has no explicit
  reveal path, or cannot return to its hidden state.

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
    visibility_plan_reviewed: bool = False
    all_content_candidates_classified: bool = False
    typed_user_need_refs_reviewed: bool = False
    control_label_exemptions_scoped: bool = False
    no_internal_content_mapped_to_ui: bool = False
    on_demand_default_hidden_reviewed: bool = False
    all_visibility_mapping_states_reviewed: bool = False
    on_demand_reveal_paths_reviewed: bool = False
    on_demand_return_paths_reviewed: bool = False
    on_demand_affordance_feedback_reviewed: bool = False
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
    implementation_content_evidence_structured: bool = False
    implementation_content_evidence_content_exact: bool = False
    clickthrough_evidence_reviewed: bool = False
    implementation_evidence_fresh: bool = False
    skill_documented: bool = False
    release_claim: str = "none"
    implemented_ui_claim: str = "none"

    def content_visibility_ready(self) -> bool:
        return (
            self.visibility_plan_reviewed
            and self.all_content_candidates_classified
            and self.typed_user_need_refs_reviewed
            and self.control_label_exemptions_scoped
            and self.no_internal_content_mapped_to_ui
            and self.on_demand_default_hidden_reviewed
            and self.all_visibility_mapping_states_reviewed
            and self.on_demand_reveal_paths_reviewed
            and self.on_demand_return_paths_reviewed
            and self.on_demand_affordance_feedback_reviewed
        )


class CorrectUiFlowStructureRollout:
    name = "CorrectUiFlowStructureRollout"
    reads = (
        "ui_model_created",
        "ui_model_reviewed",
        "visibility_plan_reviewed",
        "all_content_candidates_classified",
        "typed_user_need_refs_reviewed",
        "control_label_exemptions_scoped",
        "no_internal_content_mapped_to_ui",
        "on_demand_default_hidden_reviewed",
        "all_visibility_mapping_states_reviewed",
        "on_demand_reveal_paths_reviewed",
        "on_demand_return_paths_reviewed",
        "on_demand_affordance_feedback_reviewed",
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
        "implementation_content_evidence_structured",
        "implementation_content_evidence_content_exact",
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
        if action == "review_content_visibility_plan":
            if not state.ui_model_reviewed:
                yield FunctionResult(
                    RolloutOutput("content_visibility_review_rejected"),
                    state,
                    label="content_visibility_review_rejected",
                )
                return
            yield FunctionResult(
                RolloutOutput("content_visibility_plan_reviewed"),
                replace(
                    state,
                    visibility_plan_reviewed=True,
                    all_content_candidates_classified=True,
                    typed_user_need_refs_reviewed=True,
                    control_label_exemptions_scoped=True,
                    no_internal_content_mapped_to_ui=True,
                    on_demand_default_hidden_reviewed=True,
                    all_visibility_mapping_states_reviewed=True,
                    on_demand_reveal_paths_reviewed=True,
                    on_demand_return_paths_reviewed=True,
                    on_demand_affordance_feedback_reviewed=True,
                ),
                label="content_visibility_plan_reviewed",
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
            if not (
                state.ui_model_reviewed
                and state.content_visibility_ready()
                and state.journey_coverage_reviewed
            ):
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
                and state.content_visibility_ready()
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
                    implementation_content_evidence_structured=True,
                    implementation_content_evidence_content_exact=True,
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
                and state.content_visibility_ready()
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
                and state.content_visibility_ready()
                and state.feature_contracts_aligned
                and state.implementation_validation_reviewed
                and state.implementation_content_evidence_structured
                and state.implementation_content_evidence_content_exact
                and state.clickthrough_evidence_reviewed
                and state.implementation_evidence_fresh
            )
            yield FunctionResult(
                RolloutOutput("implemented_ui_accepted" if accepted else "implemented_ui_rejected"),
                replace(state, implemented_ui_claim="accepted" if accepted else "rejected"),
                label="implemented_ui_accepted" if accepted else "implemented_ui_rejected",
            )


class BrokenVisibilityAdmissionRollout(CorrectUiFlowStructureRollout):
    """Known-bad base that lets a visibility defect survive to a broad claim."""

    visibility_plan_reviewed = True
    all_content_candidates_classified = True
    typed_user_need_refs_reviewed = True
    control_label_exemptions_scoped = True
    no_internal_content_mapped_to_ui = True
    on_demand_default_hidden_reviewed = True
    all_visibility_mapping_states_reviewed = True
    on_demand_reveal_paths_reviewed = True
    on_demand_return_paths_reviewed = True
    on_demand_affordance_feedback_reviewed = True
    visibility_review_status = "content_visibility_reviewed_with_gap"

    def apply(self, input_obj: RolloutAction, state: RolloutState) -> Iterable[FunctionResult]:
        action = input_obj.action_type
        if action == "review_content_visibility_plan":
            if not state.ui_model_reviewed:
                yield FunctionResult(
                    RolloutOutput("content_visibility_review_rejected"),
                    state,
                    label="content_visibility_review_rejected",
                )
                return
            yield FunctionResult(
                RolloutOutput(self.visibility_review_status),
                replace(
                    state,
                    visibility_plan_reviewed=self.visibility_plan_reviewed,
                    all_content_candidates_classified=self.all_content_candidates_classified,
                    typed_user_need_refs_reviewed=self.typed_user_need_refs_reviewed,
                    control_label_exemptions_scoped=self.control_label_exemptions_scoped,
                    no_internal_content_mapped_to_ui=self.no_internal_content_mapped_to_ui,
                    on_demand_default_hidden_reviewed=self.on_demand_default_hidden_reviewed,
                    all_visibility_mapping_states_reviewed=self.all_visibility_mapping_states_reviewed,
                    on_demand_reveal_paths_reviewed=self.on_demand_reveal_paths_reviewed,
                    on_demand_return_paths_reviewed=self.on_demand_return_paths_reviewed,
                    on_demand_affordance_feedback_reviewed=self.on_demand_affordance_feedback_reviewed,
                ),
                label=self.visibility_review_status,
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
                RolloutOutput("structure_derived_despite_visibility_gap"),
                replace(
                    state,
                    structure_derived=True,
                    parent_child_topology_present=True,
                    redundancy_reviewed=True,
                    text_hierarchy_reviewed=True,
                    typography_handoff_guidance_reviewed=True,
                ),
                label="structure_derived_despite_visibility_gap",
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
            return
        yield from super().apply(input_obj, state)


class BrokenMissingVisibilityPlanRollout(BrokenVisibilityAdmissionRollout):
    name = "BrokenMissingVisibilityPlanRollout"
    idempotency = "Broken variant accepts display derivation without a reviewed content-visibility plan."
    visibility_plan_reviewed = False
    visibility_review_status = "visibility_plan_missing_but_continues"


class BrokenUnclassifiedContentRollout(BrokenVisibilityAdmissionRollout):
    name = "BrokenUnclassifiedContentRollout"
    idempotency = "Broken variant lets unclassified candidate content enter ordinary UI modeling."
    all_content_candidates_classified = False
    visibility_review_status = "unclassified_content_accepted"


class BrokenUntypedUserNeedRollout(BrokenVisibilityAdmissionRollout):
    name = "BrokenUntypedUserNeedRollout"
    idempotency = "Broken variant accepts arbitrary non-empty strings as user-need evidence."
    typed_user_need_refs_reviewed = False
    visibility_review_status = "untyped_user_need_accepted"


class BrokenOverbroadControlLabelExemptionRollout(BrokenVisibilityAdmissionRollout):
    name = "BrokenOverbroadControlLabelExemptionRollout"
    idempotency = "Broken variant lets state or metadata text masquerade as a task-owned control label."
    control_label_exemptions_scoped = False
    visibility_review_status = "overbroad_control_label_exemption_accepted"


class BrokenInternalContentMappedRollout(BrokenVisibilityAdmissionRollout):
    name = "BrokenInternalContentMappedRollout"
    idempotency = "Broken variant lets internal content map to an ordinary UI owner."
    no_internal_content_mapped_to_ui = False
    visibility_review_status = "internal_content_mapping_accepted"


class BrokenOnDemandDefaultVisibleRollout(BrokenVisibilityAdmissionRollout):
    name = "BrokenOnDemandDefaultVisibleRollout"
    idempotency = "Broken variant accepts user-on-demand content that is visible in the closed state."
    on_demand_default_hidden_reviewed = False
    visibility_review_status = "on_demand_default_visible_accepted"


class BrokenOnDemandMappingStateBypassRollout(BrokenVisibilityAdmissionRollout):
    name = "BrokenOnDemandMappingStateBypassRollout"
    idempotency = "Broken variant checks display state but lets text, visible-surface, or observed mappings leak while closed."
    all_visibility_mapping_states_reviewed = False
    visibility_review_status = "on_demand_non_display_state_bypass_accepted"


class BrokenOnDemandMissingRevealRollout(BrokenVisibilityAdmissionRollout):
    name = "BrokenOnDemandMissingRevealRollout"
    idempotency = "Broken variant accepts user-on-demand content without an explicit accessible reveal path."
    on_demand_reveal_paths_reviewed = False
    visibility_review_status = "on_demand_missing_reveal_accepted"


class BrokenOnDemandNoReturnRollout(BrokenVisibilityAdmissionRollout):
    name = "BrokenOnDemandNoReturnRollout"
    idempotency = "Broken variant accepts revealed user-on-demand content without a return-to-hidden path."
    on_demand_return_paths_reviewed = False
    visibility_review_status = "on_demand_missing_return_accepted"


class BrokenOnDemandAffordanceFeedbackRollout(BrokenVisibilityAdmissionRollout):
    name = "BrokenOnDemandAffordanceFeedbackRollout"
    idempotency = "Broken variant accepts hidden reveal controls or disclosure without item-bound feedback."
    on_demand_affordance_feedback_reviewed = False
    visibility_review_status = "on_demand_affordance_feedback_gap_accepted"


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
                    implementation_content_evidence_structured=True,
                    implementation_content_evidence_content_exact=True,
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
                    implementation_content_evidence_structured=True,
                    implementation_content_evidence_content_exact=True,
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
                    implementation_content_evidence_structured=True,
                    implementation_content_evidence_content_exact=True,
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


class BrokenOpaqueContentVisibilityEvidenceRollout(CorrectUiFlowStructureRollout):
    name = "BrokenOpaqueContentVisibilityEvidenceRollout"
    idempotency = "Broken variant accepts one opaque evidence reference without per-content visibility phases."

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
                    implementation_content_evidence_structured=False,
                    implementation_content_evidence_content_exact=False,
                    clickthrough_evidence_reviewed=True,
                    implementation_evidence_fresh=True,
                ),
                label="implementation_validation_reviewed_with_opaque_content_evidence",
            )
            return
        if input_obj.action_type == "claim_implemented_ui":
            accepted = (
                state.skill_documented
                and state.content_visibility_ready()
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
            return
        yield from super().apply(input_obj, state)


class BrokenCrossContentVisibilityEvidenceRollout(CorrectUiFlowStructureRollout):
    name = "BrokenCrossContentVisibilityEvidenceRollout"
    idempotency = "Broken variant accepts structured rows whose observed item belongs to different content or state."

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
                    implementation_content_evidence_structured=True,
                    implementation_content_evidence_content_exact=False,
                    clickthrough_evidence_reviewed=True,
                    implementation_evidence_fresh=True,
                ),
                label="implementation_validation_reviewed_with_cross_content_evidence",
            )
            return
        if input_obj.action_type == "claim_implemented_ui":
            accepted = (
                state.skill_documented
                and state.content_visibility_ready()
                and state.feature_contracts_aligned
                and state.implementation_validation_reviewed
                and state.implementation_content_evidence_structured
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


def terminal_predicate(current_output, state, trace) -> bool:
    del state, trace
    return isinstance(current_output, RolloutOutput) and (
        current_output.status.startswith("release_")
        or current_output.status.startswith("implemented_ui_")
    )


def _ui_claim_accepted(state: RolloutState) -> bool:
    return state.release_claim == "accepted" or state.implemented_ui_claim == "accepted"


def ui_claim_requires_visibility_plan(state: RolloutState, trace) -> InvariantResult:
    del trace
    if _ui_claim_accepted(state) and not state.visibility_plan_reviewed:
        return InvariantResult.fail("UI claim accepted without a reviewed content-visibility plan")
    return InvariantResult.pass_()


def ui_claim_requires_candidate_classification(state: RolloutState, trace) -> InvariantResult:
    del trace
    if _ui_claim_accepted(state) and not state.all_content_candidates_classified:
        return InvariantResult.fail("UI claim accepted while candidate content remains unclassified")
    return InvariantResult.pass_()


def ui_claim_requires_typed_user_need_refs(state: RolloutState, trace) -> InvariantResult:
    del trace
    if _ui_claim_accepted(state) and not state.typed_user_need_refs_reviewed:
        return InvariantResult.fail("UI claim accepted while user-facing content has untyped or unresolved need references")
    return InvariantResult.pass_()


def ui_claim_requires_scoped_control_label_exemptions(state: RolloutState, trace) -> InvariantResult:
    del trace
    if _ui_claim_accepted(state) and not state.control_label_exemptions_scoped:
        return InvariantResult.fail("UI claim accepted while state or metadata content can masquerade as a normal task-owned control label")
    return InvariantResult.pass_()


def ui_claim_forbids_internal_content_mapping(state: RolloutState, trace) -> InvariantResult:
    del trace
    if _ui_claim_accepted(state) and not state.no_internal_content_mapped_to_ui:
        return InvariantResult.fail("UI claim accepted while internal content maps to an ordinary UI surface")
    return InvariantResult.pass_()


def ui_claim_requires_on_demand_default_hidden(state: RolloutState, trace) -> InvariantResult:
    del trace
    if _ui_claim_accepted(state) and not state.on_demand_default_hidden_reviewed:
        return InvariantResult.fail("UI claim accepted while user-on-demand content is visible before reveal")
    return InvariantResult.pass_()


def ui_claim_requires_all_mapping_state_checks(state: RolloutState, trace) -> InvariantResult:
    del trace
    if _ui_claim_accepted(state) and not state.all_visibility_mapping_states_reviewed:
        return InvariantResult.fail("UI claim accepted without checking display, text, visible-surface, and observed mapping states")
    return InvariantResult.pass_()


def ui_claim_requires_on_demand_reveal_path(state: RolloutState, trace) -> InvariantResult:
    del trace
    if _ui_claim_accepted(state) and not state.on_demand_reveal_paths_reviewed:
        return InvariantResult.fail("UI claim accepted without an explicit accessible on-demand reveal path")
    return InvariantResult.pass_()


def ui_claim_requires_on_demand_return_path(state: RolloutState, trace) -> InvariantResult:
    del trace
    if _ui_claim_accepted(state) and not state.on_demand_return_paths_reviewed:
        return InvariantResult.fail("UI claim accepted without a return-to-hidden path for on-demand content")
    return InvariantResult.pass_()


def ui_claim_requires_on_demand_affordance_feedback(state: RolloutState, trace) -> InvariantResult:
    del trace
    if _ui_claim_accepted(state) and not state.on_demand_affordance_feedback_reviewed:
        return InvariantResult.fail("UI claim accepted without a visible task-owned reveal affordance and item-bound feedback")
    return InvariantResult.pass_()


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


def implemented_ui_requires_structured_content_evidence(state: RolloutState, trace) -> InvariantResult:
    del trace
    if state.implemented_ui_claim == "accepted" and not state.implementation_content_evidence_structured:
        return InvariantResult.fail("implemented UI accepted without per-content default, reveal, return, and internal-absence evidence")
    return InvariantResult.pass_()


def implemented_ui_requires_content_exact_evidence(state: RolloutState, trace) -> InvariantResult:
    del trace
    if state.implemented_ui_claim == "accepted" and not state.implementation_content_evidence_content_exact:
        return InvariantResult.fail("implemented UI accepted with an observed item for different content or UI state")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "ui_claim_requires_visibility_plan",
        "Release and implemented UI claims require a reviewed content-visibility plan.",
        ui_claim_requires_visibility_plan,
    ),
    Invariant(
        "ui_claim_requires_candidate_classification",
        "Release and implemented UI claims require every in-scope candidate to be classified.",
        ui_claim_requires_candidate_classification,
    ),
    Invariant(
        "ui_claim_requires_typed_user_need_refs",
        "User-facing content needs typed and resolvable task/state/recovery/safety references.",
        ui_claim_requires_typed_user_need_refs,
    ),
    Invariant(
        "ui_claim_requires_scoped_control_label_exemptions",
        "Only normal task-owned control labels without extra state or metadata are exempt from content rows.",
        ui_claim_requires_scoped_control_label_exemptions,
    ),
    Invariant(
        "ui_claim_forbids_internal_content_mapping",
        "Internal content cannot map to ordinary UI displays, text, visible surfaces, or observed content.",
        ui_claim_forbids_internal_content_mapping,
    ),
    Invariant(
        "ui_claim_requires_on_demand_default_hidden",
        "User-on-demand content must be hidden in the default or closed state.",
        ui_claim_requires_on_demand_default_hidden,
    ),
    Invariant(
        "ui_claim_requires_all_mapping_state_checks",
        "On-demand state checks cover display, text, visible-surface, and observed mappings.",
        ui_claim_requires_all_mapping_state_checks,
    ),
    Invariant(
        "ui_claim_requires_on_demand_reveal_path",
        "User-on-demand content requires an explicit reveal path with keyboard or focus equivalence.",
        ui_claim_requires_on_demand_reveal_path,
    ),
    Invariant(
        "ui_claim_requires_on_demand_return_path",
        "User-on-demand content requires a close, collapse, blur, Escape, or equivalent return path.",
        ui_claim_requires_on_demand_return_path,
    ),
    Invariant(
        "ui_claim_requires_on_demand_affordance_feedback",
        "On-demand content needs a discoverable task-owned affordance and truthful item-bound feedback.",
        ui_claim_requires_on_demand_affordance_feedback,
    ),
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
    Invariant(
        "implemented_ui_requires_structured_content_evidence",
        "Implemented UI claims require structured per-content visibility evidence.",
        implemented_ui_requires_structured_content_evidence,
    ),
    Invariant(
        "implemented_ui_requires_content_exact_evidence",
        "Implemented UI claims require each visible evidence row to resolve to the same content and state.",
        implemented_ui_requires_content_exact_evidence,
    ),
)

EXTERNAL_INPUTS = (
    RolloutAction("create_ui_model"),
    RolloutAction("review_ui_model"),
    RolloutAction("review_content_visibility_plan"),
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
    RolloutAction("review_content_visibility_plan"),
    RolloutAction("review_journey_coverage"),
    RolloutAction("derive_structure"),
    RolloutAction("document_skill"),
    RolloutAction("claim_release"),
)

IMPLEMENTATION_INPUTS = (
    RolloutAction("create_ui_model"),
    RolloutAction("review_ui_model"),
    RolloutAction("review_content_visibility_plan"),
    RolloutAction("review_journey_coverage"),
    RolloutAction("derive_structure"),
    RolloutAction("review_implementation_validation"),
    RolloutAction("document_skill"),
    RolloutAction("claim_implemented_ui"),
)

MAX_SEQUENCE_LENGTH = max(len(RELEASE_INPUTS), len(IMPLEMENTATION_INPUTS))


def initial_state() -> RolloutState:
    return RolloutState()


def build_correct_workflow() -> Workflow:
    return Workflow((CorrectUiFlowStructureRollout(),), name="ui_flow_structure_correct")


def build_broken_layout_only_workflow() -> Workflow:
    return Workflow((BrokenLayoutOnlyRollout(),), name="ui_flow_structure_layout_only_broken")


def build_broken_missing_visibility_plan_workflow() -> Workflow:
    return Workflow(
        (BrokenMissingVisibilityPlanRollout(),),
        name="ui_flow_structure_missing_visibility_plan_broken",
    )


def build_broken_unclassified_content_workflow() -> Workflow:
    return Workflow(
        (BrokenUnclassifiedContentRollout(),),
        name="ui_flow_structure_unclassified_content_broken",
    )


def build_broken_untyped_user_need_workflow() -> Workflow:
    return Workflow(
        (BrokenUntypedUserNeedRollout(),),
        name="ui_flow_structure_untyped_user_need_broken",
    )


def build_broken_overbroad_control_label_exemption_workflow() -> Workflow:
    return Workflow(
        (BrokenOverbroadControlLabelExemptionRollout(),),
        name="ui_flow_structure_overbroad_control_label_exemption_broken",
    )


def build_broken_internal_content_mapping_workflow() -> Workflow:
    return Workflow(
        (BrokenInternalContentMappedRollout(),),
        name="ui_flow_structure_internal_content_mapping_broken",
    )


def build_broken_on_demand_default_visible_workflow() -> Workflow:
    return Workflow(
        (BrokenOnDemandDefaultVisibleRollout(),),
        name="ui_flow_structure_on_demand_default_visible_broken",
    )


def build_broken_on_demand_mapping_state_bypass_workflow() -> Workflow:
    return Workflow(
        (BrokenOnDemandMappingStateBypassRollout(),),
        name="ui_flow_structure_on_demand_mapping_state_bypass_broken",
    )


def build_broken_on_demand_missing_reveal_workflow() -> Workflow:
    return Workflow(
        (BrokenOnDemandMissingRevealRollout(),),
        name="ui_flow_structure_on_demand_missing_reveal_broken",
    )


def build_broken_on_demand_no_return_workflow() -> Workflow:
    return Workflow(
        (BrokenOnDemandNoReturnRollout(),),
        name="ui_flow_structure_on_demand_no_return_broken",
    )


def build_broken_on_demand_affordance_feedback_workflow() -> Workflow:
    return Workflow(
        (BrokenOnDemandAffordanceFeedbackRollout(),),
        name="ui_flow_structure_on_demand_affordance_feedback_broken",
    )


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


def build_broken_opaque_content_visibility_evidence_workflow() -> Workflow:
    return Workflow(
        (BrokenOpaqueContentVisibilityEvidenceRollout(),),
        name="ui_flow_structure_opaque_content_visibility_evidence_broken",
    )


def build_broken_cross_content_visibility_evidence_workflow() -> Workflow:
    return Workflow(
        (BrokenCrossContentVisibilityEvidenceRollout(),),
        name="ui_flow_structure_cross_content_visibility_evidence_broken",
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
    "build_broken_internal_content_mapping_workflow",
    "build_broken_cross_content_visibility_evidence_workflow",
    "build_broken_opaque_content_visibility_evidence_workflow",
    "build_broken_overbroad_control_label_exemption_workflow",
    "build_broken_implementation_without_clickthrough_workflow",
    "build_broken_implementation_without_feature_alignment_workflow",
    "build_broken_missing_visibility_plan_workflow",
    "build_broken_no_journey_coverage_workflow",
    "build_broken_no_typography_handoff_workflow",
    "build_broken_no_visible_branch_coverage_workflow",
    "build_broken_no_topology_workflow",
    "build_broken_on_demand_default_visible_workflow",
    "build_broken_on_demand_mapping_state_bypass_workflow",
    "build_broken_on_demand_missing_reveal_workflow",
    "build_broken_on_demand_no_return_workflow",
    "build_broken_on_demand_affordance_feedback_workflow",
    "build_broken_stale_implementation_evidence_workflow",
    "build_broken_unclassified_content_workflow",
    "build_broken_untyped_user_need_workflow",
    "build_correct_workflow",
    "initial_state",
    "terminal_predicate",
]
