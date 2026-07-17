"""FlowGuard rollout model for hierarchical model-mesh governance.

Risk Purpose Header:
Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: review the implementation plan for multi-level parent/child model
partition governance. It guards against treating model count as the only mesh
trigger, trusting oversized or legacy models without split review, accepting
child hierarchies with parent coverage gaps, hiding sibling overlap or ownership
conflicts, and publishing without local install, shadow workspace, Git, and
GitHub release synchronization.

Run:
python .flowguard/hierarchical_model_mesh/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from flowguard import FunctionResult, Invariant, InvariantResult, Scenario, ScenarioExpectation, Workflow
from flowguard.review import review_scenarios


@dataclass(frozen=True)
class HierarchyCase:
    name: str
    partition_map_defined: bool = True
    mesh_per_parent_boundary: bool = True
    quantity_trigger: bool = True
    scale_trigger: bool = True
    coverage_check: bool = True
    overlap_check: bool = True
    state_ownership_check: bool = True
    side_effect_ownership_check: bool = True
    stale_and_skipped_visible: bool = True
    split_review_decisions: bool = True
    legacy_classification: bool = True
    legacy_contract_before_trust: bool = True
    no_child_graph_expansion: bool = True
    child_boundary_diff_recorded: bool = True
    bug_class_boundary_not_instance: bool = True
    parent_decision_from_boundary_diff: bool = True
    parent_rerun_on_contract_drift: bool = True
    sibling_rerun_on_shared_dependency_drift: bool = True
    background_completion_evidence: bool = True
    release_sync_checks: bool = True


@dataclass(frozen=True)
class HierarchyPlan:
    case_name: str = ""
    partition_map_defined: bool = False
    mesh_per_parent_boundary: bool = False
    quantity_trigger: bool = False
    scale_trigger: bool = False
    coverage_check: bool = False
    overlap_check: bool = False
    state_ownership_check: bool = False
    side_effect_ownership_check: bool = False
    stale_and_skipped_visible: bool = False
    split_review_decisions: bool = False
    legacy_classification: bool = False
    legacy_contract_before_trust: bool = False
    no_child_graph_expansion: bool = False
    child_boundary_diff_recorded: bool = False
    bug_class_boundary_not_instance: bool = False
    parent_decision_from_boundary_diff: bool = False
    parent_rerun_on_contract_drift: bool = False
    sibling_rerun_on_shared_dependency_drift: bool = False
    background_completion_evidence: bool = False
    release_sync_checks: bool = False


GOOD_PLAN = HierarchyCase("good_hierarchical_mesh_plan")
BROKEN_NO_SCALE_TRIGGER = HierarchyCase("broken_no_scale_trigger", scale_trigger=False)
BROKEN_COVERAGE_GAP = HierarchyCase("broken_coverage_gap", coverage_check=False)
BROKEN_OVERLAP_HIDDEN = HierarchyCase("broken_overlap_hidden", overlap_check=False)
BROKEN_STATE_OWNER_CONFLICT = HierarchyCase("broken_state_owner_conflict", state_ownership_check=False)
BROKEN_SIDE_EFFECT_OWNER_CONFLICT = HierarchyCase("broken_side_effect_owner_conflict", side_effect_ownership_check=False)
BROKEN_LEGACY_DIRECT_TRUST = HierarchyCase("broken_legacy_direct_trust", legacy_contract_before_trust=False)
BROKEN_CHILD_GRAPH_EXPANSION = HierarchyCase("broken_child_graph_expansion", no_child_graph_expansion=False)
BROKEN_NO_BOUNDARY_DIFF = HierarchyCase("broken_no_boundary_diff", child_boundary_diff_recorded=False)
BROKEN_BUG_INSTANCE_BOUNDARY = HierarchyCase(
    "broken_bug_instance_boundary",
    bug_class_boundary_not_instance=False,
)
BROKEN_PARENT_IGNORES_DIFF = HierarchyCase(
    "broken_parent_ignores_diff",
    parent_decision_from_boundary_diff=False,
)
BROKEN_PARENT_SKIPS_CONTRACT_DRIFT = HierarchyCase(
    "broken_parent_skips_contract_drift",
    parent_rerun_on_contract_drift=False,
)
BROKEN_SIBLING_STALE_AFTER_SHARED_DRIFT = HierarchyCase(
    "broken_sibling_stale_after_shared_drift",
    sibling_rerun_on_shared_dependency_drift=False,
)
BROKEN_BACKGROUND_OVERCLAIM = HierarchyCase("broken_background_overclaim", background_completion_evidence=False)
BROKEN_RELEASE_SYNC_OMITTED = HierarchyCase("broken_release_sync_omitted", release_sync_checks=False)


class EvaluateHierarchyPlan:
    name = "EvaluateHierarchyPlan"
    reads = ("HierarchyPlan",)
    writes = (
        "case_name",
        "partition_map_defined",
        "mesh_per_parent_boundary",
        "quantity_trigger",
        "scale_trigger",
        "coverage_check",
        "overlap_check",
        "state_ownership_check",
        "side_effect_ownership_check",
        "stale_and_skipped_visible",
        "split_review_decisions",
        "legacy_classification",
        "legacy_contract_before_trust",
        "no_child_graph_expansion",
        "child_boundary_diff_recorded",
        "bug_class_boundary_not_instance",
        "parent_decision_from_boundary_diff",
        "parent_rerun_on_contract_drift",
        "sibling_rerun_on_shared_dependency_drift",
        "background_completion_evidence",
        "release_sync_checks",
    )
    accepted_input_type = HierarchyCase
    input_description = "hierarchical mesh rollout case"
    output_description = "hierarchical mesh rollout plan"
    idempotency = "same case produces one rollout plan"

    def apply(self, input_obj: HierarchyCase, _state: HierarchyPlan):
        new_state = HierarchyPlan(
            case_name=input_obj.name,
            partition_map_defined=input_obj.partition_map_defined,
            mesh_per_parent_boundary=input_obj.mesh_per_parent_boundary,
            quantity_trigger=input_obj.quantity_trigger,
            scale_trigger=input_obj.scale_trigger,
            coverage_check=input_obj.coverage_check,
            overlap_check=input_obj.overlap_check,
            state_ownership_check=input_obj.state_ownership_check,
            side_effect_ownership_check=input_obj.side_effect_ownership_check,
            stale_and_skipped_visible=input_obj.stale_and_skipped_visible,
            split_review_decisions=input_obj.split_review_decisions,
            legacy_classification=input_obj.legacy_classification,
            legacy_contract_before_trust=input_obj.legacy_contract_before_trust,
            no_child_graph_expansion=input_obj.no_child_graph_expansion,
            child_boundary_diff_recorded=input_obj.child_boundary_diff_recorded,
            bug_class_boundary_not_instance=input_obj.bug_class_boundary_not_instance,
            parent_decision_from_boundary_diff=input_obj.parent_decision_from_boundary_diff,
            parent_rerun_on_contract_drift=input_obj.parent_rerun_on_contract_drift,
            sibling_rerun_on_shared_dependency_drift=input_obj.sibling_rerun_on_shared_dependency_drift,
            background_completion_evidence=input_obj.background_completion_evidence,
            release_sync_checks=input_obj.release_sync_checks,
        )
        return (
            FunctionResult(
                output=input_obj,
                new_state=new_state,
                label=input_obj.name,
                reason="projected hierarchy rollout decision into policy state",
            ),
        )


def _pass() -> InvariantResult:
    return InvariantResult.pass_()


def _fail(name: str, message: str) -> InvariantResult:
    return InvariantResult.fail(message, {"violation": name})


def _empty(state: HierarchyPlan) -> bool:
    return not state.case_name


def partition_map_and_multilevel_mesh_exist(state: HierarchyPlan, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.partition_map_defined:
        return _fail("partition_map_and_multilevel_mesh_exist", "parent boundary lacks a partition map")
    if not state.mesh_per_parent_boundary:
        return _fail(
            "partition_map_and_multilevel_mesh_exist",
            "nested child domains need their own parent-boundary mesh review",
        )
    return _pass()


def mesh_triggers_include_quantity_and_scale(state: HierarchyPlan, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.quantity_trigger:
        return _fail("mesh_triggers_include_quantity_and_scale", "model-count trigger is missing")
    if not state.scale_trigger:
        return _fail(
            "mesh_triggers_include_quantity_and_scale",
            "large single-model state space does not trigger split review",
        )
    return _pass()


def coverage_and_overlap_are_checked(state: HierarchyPlan, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.coverage_check:
        return _fail("coverage_and_overlap_are_checked", "child models do not cover the parent space")
    if not state.overlap_check:
        return _fail("coverage_and_overlap_are_checked", "sibling model overlap is not reviewed")
    return _pass()


def ownership_conflicts_are_blockers(state: HierarchyPlan, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.state_ownership_check:
        return _fail("ownership_conflicts_are_blockers", "duplicate state-write ownership is hidden")
    if not state.side_effect_ownership_check:
        return _fail("ownership_conflicts_are_blockers", "duplicate side-effect ownership is hidden")
    return _pass()


def evidence_and_split_decisions_stay_explicit(state: HierarchyPlan, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.stale_and_skipped_visible:
        return _fail("evidence_and_split_decisions_stay_explicit", "stale/skipped evidence is hidden")
    if not state.split_review_decisions:
        return _fail("evidence_and_split_decisions_stay_explicit", "oversized models lack split decisions")
    return _pass()


def legacy_models_are_wrapped_before_trust(state: HierarchyPlan, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.legacy_classification:
        return _fail("legacy_models_are_wrapped_before_trust", "legacy models are not classified")
    if not state.legacy_contract_before_trust:
        return _fail(
            "legacy_models_are_wrapped_before_trust",
            "legacy model is trusted before a compatibility contract exists",
        )
    return _pass()


def mesh_does_not_expand_child_graphs(state: HierarchyPlan, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.no_child_graph_expansion:
        return _fail("mesh_does_not_expand_child_graphs", "mesh inlines child state graphs")
    return _pass()


def child_boundary_changes_propagate_upward(state: HierarchyPlan, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.child_boundary_diff_recorded:
        return _fail(
            "child_boundary_changes_propagate_upward",
            "child update lacks a compact boundary diff for parent review",
        )
    if not state.parent_decision_from_boundary_diff:
        return _fail(
            "child_boundary_changes_propagate_upward",
            "parent does not classify the child boundary diff before claiming confidence",
        )
    if not state.parent_rerun_on_contract_drift:
        return _fail(
            "child_boundary_changes_propagate_upward",
            "input/output/state/side-effect/contract drift does not require parent rerun",
        )
    if not state.sibling_rerun_on_shared_dependency_drift:
        return _fail(
            "child_boundary_changes_propagate_upward",
            "shared dependency drift does not stale or rerun affected sibling models",
        )
    return _pass()


def model_miss_scope_is_bug_class_boundary(state: HierarchyPlan, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.bug_class_boundary_not_instance:
        return _fail(
            "model_miss_scope_is_bug_class_boundary",
            "model repair scopes to the observed bug instance instead of the bug-class risk boundary",
        )
    return _pass()


def background_and_release_evidence_required(state: HierarchyPlan, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.background_completion_evidence:
        return _fail(
            "background_and_release_evidence_required",
            "background checks are reported without exit/log evidence",
        )
    if not state.release_sync_checks:
        return _fail(
            "background_and_release_evidence_required",
            "release lacks install, shadow workspace, Git, and GitHub sync checks",
        )
    return _pass()


INVARIANTS = (
    Invariant(
        "partition_map_and_multilevel_mesh_exist",
        "Each parent boundary has a partition map and nested children can have their own mesh.",
        partition_map_and_multilevel_mesh_exist,
    ),
    Invariant(
        "mesh_triggers_include_quantity_and_scale",
        "Mesh review triggers on model count and single-model scale.",
        mesh_triggers_include_quantity_and_scale,
    ),
    Invariant(
        "coverage_and_overlap_are_checked",
        "Mesh checks parent coverage completeness and sibling overlap.",
        coverage_and_overlap_are_checked,
    ),
    Invariant(
        "ownership_conflicts_are_blockers",
        "Mesh blocks duplicate state-write and side-effect ownership.",
        ownership_conflicts_are_blockers,
    ),
    Invariant(
        "evidence_and_split_decisions_stay_explicit",
        "Mesh exposes stale/skipped evidence and split decisions.",
        evidence_and_split_decisions_stay_explicit,
    ),
    Invariant(
        "legacy_models_are_wrapped_before_trust",
        "Legacy models are classified and wrapped before being trusted.",
        legacy_models_are_wrapped_before_trust,
    ),
    Invariant(
        "mesh_does_not_expand_child_graphs",
        "Mesh treats child models as contracts rather than expanding their graphs.",
        mesh_does_not_expand_child_graphs,
    ),
    Invariant(
        "child_boundary_changes_propagate_upward",
        "Child boundary changes produce parent decisions and rerun affected parent or sibling models.",
        child_boundary_changes_propagate_upward,
    ),
    Invariant(
        "model_miss_scope_is_bug_class_boundary",
        "Model-miss repairs scope to bug-class risk boundaries, not a single bug instance.",
        model_miss_scope_is_bug_class_boundary,
    ),
    Invariant(
        "background_and_release_evidence_required",
        "Background validation and release synchronization need concrete evidence.",
        background_and_release_evidence_required,
    ),
)


def build_workflow() -> Workflow:
    return Workflow((EvaluateHierarchyPlan(),), name="hierarchical_model_mesh_rollout")


def _expect_ok(summary: str, labels: Sequence[str] = ()) -> ScenarioExpectation:
    return ScenarioExpectation(expected_status="ok", required_trace_labels=tuple(labels), summary=summary)


def _expect_violation(summary: str, names: Sequence[str]) -> ScenarioExpectation:
    return ScenarioExpectation(
        expected_status="violation",
        expected_violation_names=tuple(names),
        summary=summary,
    )


def scenario(
    name: str,
    description: str,
    case: HierarchyCase,
    expected: ScenarioExpectation,
) -> Scenario:
    return Scenario(
        name=name,
        description=description,
        workflow=build_workflow(),
        initial_state=HierarchyPlan(),
        external_input_sequence=(case,),
        invariants=INVARIANTS,
        expected=expected,
    )


SCENARIOS = (
    scenario(
        "good_plan_passes",
        "A complete hierarchical mesh rollout plan passes.",
        GOOD_PLAN,
        _expect_ok("complete plan passes", labels=("good_hierarchical_mesh_plan",)),
    ),
    scenario(
        "scale_trigger_required",
        "A single huge model must trigger split review even if model count is low.",
        BROKEN_NO_SCALE_TRIGGER,
        _expect_violation("missing large-model trigger fails", ("mesh_triggers_include_quantity_and_scale",)),
    ),
    scenario(
        "coverage_gap_fails",
        "Child models must cover the parent partition space.",
        BROKEN_COVERAGE_GAP,
        _expect_violation("coverage gap fails", ("coverage_and_overlap_are_checked",)),
    ),
    scenario(
        "overlap_review_required",
        "Sibling overlap cannot be hidden.",
        BROKEN_OVERLAP_HIDDEN,
        _expect_violation("hidden overlap fails", ("coverage_and_overlap_are_checked",)),
    ),
    scenario(
        "state_owner_conflict_fails",
        "Duplicate state-write owners must block green continuation.",
        BROKEN_STATE_OWNER_CONFLICT,
        _expect_violation("state ownership conflict fails", ("ownership_conflicts_are_blockers",)),
    ),
    scenario(
        "side_effect_owner_conflict_fails",
        "Duplicate side-effect owners must block green continuation.",
        BROKEN_SIDE_EFFECT_OWNER_CONFLICT,
        _expect_violation("side-effect ownership conflict fails", ("ownership_conflicts_are_blockers",)),
    ),
    scenario(
        "legacy_contract_required",
        "Legacy models cannot become strong child evidence before compatibility wrapping.",
        BROKEN_LEGACY_DIRECT_TRUST,
        _expect_violation("legacy direct trust fails", ("legacy_models_are_wrapped_before_trust",)),
    ),
    scenario(
        "mesh_cannot_inline_child_graphs",
        "Mesh review must not recreate the giant state graph.",
        BROKEN_CHILD_GRAPH_EXPANSION,
        _expect_violation("child graph expansion fails", ("mesh_does_not_expand_child_graphs",)),
    ),
    scenario(
        "child_boundary_diff_required",
        "A repaired child model must expose a compact boundary diff before parent confidence.",
        BROKEN_NO_BOUNDARY_DIFF,
        _expect_violation("missing boundary diff fails", ("child_boundary_changes_propagate_upward",)),
    ),
    scenario(
        "bug_instance_scope_rejected",
        "The observed bug can be holdout evidence but not the whole model boundary.",
        BROKEN_BUG_INSTANCE_BOUNDARY,
        _expect_violation("bug instance boundary fails", ("model_miss_scope_is_bug_class_boundary",)),
    ),
    scenario(
        "parent_must_classify_boundary_diff",
        "A parent must classify a child boundary diff before consuming new child evidence.",
        BROKEN_PARENT_IGNORES_DIFF,
        _expect_violation("parent diff omission fails", ("child_boundary_changes_propagate_upward",)),
    ),
    scenario(
        "parent_rerun_required_on_contract_drift",
        "Input, output, state, side-effect, or outgoing-contract drift requires parent rerun.",
        BROKEN_PARENT_SKIPS_CONTRACT_DRIFT,
        _expect_violation("parent contract drift omission fails", ("child_boundary_changes_propagate_upward",)),
    ),
    scenario(
        "affected_sibling_models_become_stale",
        "A child boundary change that alters shared dependencies must rerun or stale affected siblings.",
        BROKEN_SIBLING_STALE_AFTER_SHARED_DRIFT,
        _expect_violation("sibling stale omission fails", ("child_boundary_changes_propagate_upward",)),
    ),
    scenario(
        "background_evidence_required",
        "Background checks need exit/log evidence before release claims.",
        BROKEN_BACKGROUND_OVERCLAIM,
        _expect_violation("background overclaim fails", ("background_and_release_evidence_required",)),
    ),
    scenario(
        "release_sync_required",
        "Release must include local install, shadow workspace, Git, and GitHub synchronization.",
        BROKEN_RELEASE_SYNC_OMITTED,
        _expect_violation("release sync omission fails", ("background_and_release_evidence_required",)),
    ),
)


def run_review():
    return review_scenarios(SCENARIOS)


if __name__ == "__main__":
    report = run_review()
    print(report.format_text())
    raise SystemExit(0 if report.ok else 1)


from flowguard.skill_contract_model import (  # noqa: E402
    FLOWGUARD_MODEL_MARKER,
    build_skill_contract_model_export,
)


def export_contract_model():
    """Project the existing hierarchical-model-mesh owner for SkillGuard V2."""

    return build_skill_contract_model_export(
        skill_id="flowguard-model-mesh",
        route_id="model_mesh_maintenance",
        owner_id="model_mesh_maintenance",
        parent_model_id="flowguard.model_first_function_flow",
        business_intent="Govern parent-child model partitions, reattachment, evidence consumption, and closure liveness.",
        claim_boundary="Projection only; target-split, sibling, reattachment, receipt, and liveness checks remain native FlowGuard authority.",
    )
