"""FlowGuard rollout model for hierarchical model-mesh governance.

Risk Purpose Header:
Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: review the implementation plan for multi-level parent/child model
partition governance. It guards against treating model count as a mesh trigger,
omitting semantic topology triggers, trusting oversized or legacy models without split review, accepting
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
    semantic_topology_trigger: bool = True
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
    root_sentinel_present: bool = True
    root_sentinel_unique: bool = True
    structural_parent_unique: bool = True
    cross_boundary_support_non_structural: bool = True
    full_parent_receipt_composition_only: bool = True
    child_receipt_coverage_exact: bool = True
    child_receipts_exact_current: bool = True
    child_receipts_owner_bound: bool = True
    child_receipts_distinct: bool = True
    feedback_relation_classification_complete: bool = True
    feedback_progress_contract_present: bool = True
    retry_progress_contract_present: bool = True
    repair_progress_contract_present: bool = True
    feedback_progress_contract_exact_current: bool = True
    feedback_progress_evidence_exact_current: bool = True
    checked_in_declaration_not_child_currentness: bool = True
    checked_in_declaration_not_progress_currentness: bool = True


@dataclass(frozen=True)
class HierarchyPlan:
    case_name: str = ""
    partition_map_defined: bool = False
    mesh_per_parent_boundary: bool = False
    semantic_topology_trigger: bool = False
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
    root_sentinel_present: bool = False
    root_sentinel_unique: bool = False
    structural_parent_unique: bool = False
    cross_boundary_support_non_structural: bool = False
    full_parent_receipt_composition_only: bool = False
    child_receipt_coverage_exact: bool = False
    child_receipts_exact_current: bool = False
    child_receipts_owner_bound: bool = False
    child_receipts_distinct: bool = False
    feedback_relation_classification_complete: bool = False
    feedback_progress_contract_present: bool = False
    retry_progress_contract_present: bool = False
    repair_progress_contract_present: bool = False
    feedback_progress_contract_exact_current: bool = False
    feedback_progress_evidence_exact_current: bool = False
    checked_in_declaration_not_child_currentness: bool = False
    checked_in_declaration_not_progress_currentness: bool = False


GOOD_PLAN = HierarchyCase("good_hierarchical_mesh_plan")
BROKEN_NO_SEMANTIC_TOPOLOGY_TRIGGER = HierarchyCase(
    "broken_no_semantic_topology_trigger",
    semantic_topology_trigger=False,
)
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
BROKEN_MISSING_ROOT_SENTINEL = HierarchyCase(
    "broken_missing_root_sentinel",
    root_sentinel_present=False,
)
BROKEN_DUPLICATE_ROOT_SENTINEL = HierarchyCase(
    "broken_duplicate_root_sentinel",
    root_sentinel_unique=False,
)
BROKEN_SECOND_STRUCTURAL_PARENT = HierarchyCase(
    "broken_second_structural_parent",
    structural_parent_unique=False,
)
BROKEN_CROSS_BOUNDARY_AS_PARENT = HierarchyCase(
    "broken_cross_boundary_as_parent",
    cross_boundary_support_non_structural=False,
)
BROKEN_PARENT_RECEIPT_AS_CHILD_RECEIPTS = HierarchyCase(
    "broken_parent_receipt_as_child_receipts",
    full_parent_receipt_composition_only=False,
)
BROKEN_CHILD_RECEIPT_COVERAGE = HierarchyCase(
    "broken_child_receipt_coverage",
    child_receipt_coverage_exact=False,
)
BROKEN_STALE_CHILD_RECEIPT = HierarchyCase(
    "broken_stale_child_receipt",
    child_receipts_exact_current=False,
)
BROKEN_FOREIGN_CHILD_RECEIPT = HierarchyCase(
    "broken_foreign_child_receipt",
    child_receipts_owner_bound=False,
)
BROKEN_DUPLICATE_CHILD_RECEIPT = HierarchyCase(
    "broken_duplicate_child_receipt",
    child_receipts_distinct=False,
)
BROKEN_INCOMPLETE_FEEDBACK_RELATION_CLASSIFICATION = HierarchyCase(
    "broken_incomplete_feedback_relation_classification",
    feedback_relation_classification_complete=False,
)
BROKEN_MISSING_FEEDBACK_PROGRESS = HierarchyCase(
    "broken_missing_feedback_progress",
    feedback_progress_contract_present=False,
)
BROKEN_MISSING_RETRY_PROGRESS = HierarchyCase(
    "broken_missing_retry_progress",
    retry_progress_contract_present=False,
)
BROKEN_MISSING_REPAIR_PROGRESS = HierarchyCase(
    "broken_missing_repair_progress",
    repair_progress_contract_present=False,
)
BROKEN_STALE_FEEDBACK_PROGRESS_CONTRACT = HierarchyCase(
    "broken_stale_feedback_progress_contract",
    feedback_progress_contract_exact_current=False,
)
BROKEN_STALE_FEEDBACK_PROGRESS = HierarchyCase(
    "broken_stale_feedback_progress",
    feedback_progress_evidence_exact_current=False,
)
BROKEN_DECLARATION_SELF_CERTIFIES_CHILD = HierarchyCase(
    "broken_declaration_self_certifies_child",
    checked_in_declaration_not_child_currentness=False,
)
BROKEN_DECLARATION_SELF_CERTIFIES_PROGRESS = HierarchyCase(
    "broken_declaration_self_certifies_progress",
    checked_in_declaration_not_progress_currentness=False,
)


class EvaluateHierarchyPlan:
    name = "EvaluateHierarchyPlan"
    reads = ("HierarchyPlan",)
    writes = (
        "case_name",
        "partition_map_defined",
        "mesh_per_parent_boundary",
        "semantic_topology_trigger",
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
        "root_sentinel_present",
        "root_sentinel_unique",
        "structural_parent_unique",
        "cross_boundary_support_non_structural",
        "full_parent_receipt_composition_only",
        "child_receipt_coverage_exact",
        "child_receipts_exact_current",
        "child_receipts_owner_bound",
        "child_receipts_distinct",
        "feedback_relation_classification_complete",
        "feedback_progress_contract_present",
        "retry_progress_contract_present",
        "repair_progress_contract_present",
        "feedback_progress_contract_exact_current",
        "feedback_progress_evidence_exact_current",
        "checked_in_declaration_not_child_currentness",
        "checked_in_declaration_not_progress_currentness",
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
            semantic_topology_trigger=input_obj.semantic_topology_trigger,
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
            root_sentinel_present=input_obj.root_sentinel_present,
            root_sentinel_unique=input_obj.root_sentinel_unique,
            structural_parent_unique=input_obj.structural_parent_unique,
            cross_boundary_support_non_structural=input_obj.cross_boundary_support_non_structural,
            full_parent_receipt_composition_only=input_obj.full_parent_receipt_composition_only,
            child_receipt_coverage_exact=input_obj.child_receipt_coverage_exact,
            child_receipts_exact_current=input_obj.child_receipts_exact_current,
            child_receipts_owner_bound=input_obj.child_receipts_owner_bound,
            child_receipts_distinct=input_obj.child_receipts_distinct,
            feedback_relation_classification_complete=input_obj.feedback_relation_classification_complete,
            feedback_progress_contract_present=input_obj.feedback_progress_contract_present,
            retry_progress_contract_present=input_obj.retry_progress_contract_present,
            repair_progress_contract_present=input_obj.repair_progress_contract_present,
            feedback_progress_contract_exact_current=input_obj.feedback_progress_contract_exact_current,
            feedback_progress_evidence_exact_current=input_obj.feedback_progress_evidence_exact_current,
            checked_in_declaration_not_child_currentness=input_obj.checked_in_declaration_not_child_currentness,
            checked_in_declaration_not_progress_currentness=input_obj.checked_in_declaration_not_progress_currentness,
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


def mesh_triggers_are_semantic_and_scale_aware(state: HierarchyPlan, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.semantic_topology_trigger:
        return _fail(
            "mesh_triggers_are_semantic_and_scale_aware",
            "affected relationships, whole-flow scope, or stale child evidence do not trigger mesh review",
        )
    if not state.scale_trigger:
        return _fail(
            "mesh_triggers_are_semantic_and_scale_aware",
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


def structural_parenthood_is_unique_and_typed(
    state: HierarchyPlan, _trace: object
) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.root_sentinel_present:
        return _fail(
            "structural_parenthood_is_unique_and_typed",
            "the topology has no node that declares the root sentinel",
        )
    if not state.root_sentinel_unique:
        return _fail(
            "structural_parenthood_is_unique_and_typed",
            "more than one topology node declares the root sentinel",
        )
    if not state.structural_parent_unique:
        return _fail(
            "structural_parenthood_is_unique_and_typed",
            "one child model has more than one structural parent",
        )
    if not state.cross_boundary_support_non_structural:
        return _fail(
            "structural_parenthood_is_unique_and_typed",
            "a cross-boundary support relation is being counted as a second structural parent",
        )
    return _pass()


def child_receipts_are_exact_current_owner_bound_and_distinct(
    state: HierarchyPlan, _trace: object
) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.full_parent_receipt_composition_only:
        return _fail(
            "child_receipts_are_exact_current_owner_bound_and_distinct",
            "a full parent receipt is being reused as proof for individual child models",
        )
    if not state.child_receipt_coverage_exact:
        return _fail(
            "child_receipts_are_exact_current_owner_bound_and_distinct",
            "the exact declared child-model set is not covered by one receipt per child",
        )
    if not state.child_receipts_exact_current:
        return _fail(
            "child_receipts_are_exact_current_owner_bound_and_distinct",
            "a missing, stale, scoped, foreign-revision, or non-terminal child receipt was accepted",
        )
    if not state.child_receipts_owner_bound:
        return _fail(
            "child_receipts_are_exact_current_owner_bound_and_distinct",
            "a child receipt does not bind the exact child model and execution owner",
        )
    if not state.child_receipts_distinct:
        return _fail(
            "child_receipts_are_exact_current_owner_bound_and_distinct",
            "the same receipt identity is projected into more than one child-model evidence slot",
        )
    return _pass()


def feedback_loops_require_current_progress_contracts(
    state: HierarchyPlan, _trace: object
) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.feedback_relation_classification_complete:
        return _fail(
            "feedback_loops_require_current_progress_contracts",
            "feedback, retry, and repair relations are not completely classified into the bounded feedback graph",
        )
    if not state.feedback_progress_contract_present:
        return _fail(
            "feedback_loops_require_current_progress_contracts",
            "an explicit feedback SCC has no declared progress contract",
        )
    if not state.retry_progress_contract_present:
        return _fail(
            "feedback_loops_require_current_progress_contracts",
            "a retry SCC has no declared progress contract",
        )
    if not state.repair_progress_contract_present:
        return _fail(
            "feedback_loops_require_current_progress_contracts",
            "a repair SCC has no declared progress contract",
        )
    if not state.feedback_progress_contract_exact_current:
        return _fail(
            "feedback_loops_require_current_progress_contracts",
            "a typed feedback, retry, or repair SCC uses a stale, foreign, or cross-revision progress contract",
        )
    if not state.feedback_progress_evidence_exact_current:
        return _fail(
            "feedback_loops_require_current_progress_contracts",
            "a typed feedback, retry, or repair SCC has missing, stale, foreign, or progress-only progress evidence",
        )
    return _pass()


def checked_in_declarations_cannot_self_certify_currentness(
    state: HierarchyPlan, _trace: object
) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.checked_in_declaration_not_child_currentness:
        return _fail(
            "checked_in_declarations_cannot_self_certify_currentness",
            "the checked-in topology declaration is being used as its own child-evidence freshness proof",
        )
    if not state.checked_in_declaration_not_progress_currentness:
        return _fail(
            "checked_in_declarations_cannot_self_certify_currentness",
            "the checked-in progress declaration is being used as its own current progress evidence",
        )
    return _pass()


INVARIANTS = (
    Invariant(
        "partition_map_and_multilevel_mesh_exist",
        "Each parent boundary has a partition map and nested children can have their own mesh.",
        partition_map_and_multilevel_mesh_exist,
    ),
    Invariant(
        "mesh_triggers_are_semantic_and_scale_aware",
        "Mesh review is triggered by semantic topology or single-model scale, never raw model count.",
        mesh_triggers_are_semantic_and_scale_aware,
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
    Invariant(
        "structural_parenthood_is_unique_and_typed",
        "The topology has exactly one root sentinel; each child has one structural parent; cross-boundary support remains non-structural.",
        structural_parenthood_is_unique_and_typed,
    ),
    Invariant(
        "child_receipts_are_exact_current_owner_bound_and_distinct",
        "A full parent receipt proves composition while every child keeps exact-current, owner-bound, distinct evidence.",
        child_receipts_are_exact_current_owner_bound_and_distinct,
    ),
    Invariant(
        "feedback_loops_require_current_progress_contracts",
        "Feedback relation classification is complete, and every feedback, retry, or repair SCC has a current progress contract and current evidence.",
        feedback_loops_require_current_progress_contracts,
    ),
    Invariant(
        "checked_in_declarations_cannot_self_certify_currentness",
        "Checked-in semantic declarations cannot prove their own child or progress currentness.",
        checked_in_declarations_cannot_self_certify_currentness,
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
        "good_typed_current_topology_evidence_passes",
        "One root sentinel, one structural parent per child, complete feedback classification, distinct child receipts, and current feedback, retry, and repair progress evidence pass together.",
        HierarchyCase("good_typed_current_topology_evidence"),
        _expect_ok(
            "typed current topology evidence passes",
            labels=("good_typed_current_topology_evidence",),
        ),
    ),
    scenario(
        "semantic_topology_trigger_required",
        "Related-model or whole-flow semantics must trigger mesh review without using raw quantity.",
        BROKEN_NO_SEMANTIC_TOPOLOGY_TRIGGER,
        _expect_violation(
            "missing semantic topology trigger fails",
            ("mesh_triggers_are_semantic_and_scale_aware",),
        ),
    ),
    scenario(
        "scale_trigger_required",
        "A single huge model must trigger split review even if model count is low.",
        BROKEN_NO_SCALE_TRIGGER,
        _expect_violation("missing large-model trigger fails", ("mesh_triggers_are_semantic_and_scale_aware",)),
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
    scenario(
        "topology_requires_one_root_sentinel",
        "A topology with zero root-sentinel nodes is rejected by the same root-cardinality invariant as a duplicate root.",
        BROKEN_MISSING_ROOT_SENTINEL,
        _expect_violation(
            "missing root sentinel fails",
            ("structural_parenthood_is_unique_and_typed",),
        ),
    ),
    scenario(
        "topology_rejects_two_root_sentinels",
        "A topology with two root-sentinel nodes is rejected by the same root-cardinality invariant as a missing root.",
        BROKEN_DUPLICATE_ROOT_SENTINEL,
        _expect_violation(
            "duplicate root sentinel fails",
            ("structural_parenthood_is_unique_and_typed",),
        ),
    ),
    scenario(
        "one_child_cannot_have_two_structural_parents",
        "A child model has exactly one structural parent in the hierarchy.",
        BROKEN_SECOND_STRUCTURAL_PARENT,
        _expect_violation(
            "a second structural parent fails",
            ("structural_parenthood_is_unique_and_typed",),
        ),
    ),
    scenario(
        "cross_boundary_support_cannot_masquerade_as_parent",
        "Cross-boundary support may connect models but cannot become another structural parent.",
        BROKEN_CROSS_BOUNDARY_AS_PARENT,
        _expect_violation(
            "cross-boundary support promoted to parent fails",
            ("structural_parenthood_is_unique_and_typed",),
        ),
    ),
    scenario(
        "full_parent_receipt_cannot_replace_declared_child_receipts",
        "A full parent receipt proves only the exact declared-child composition; each child still needs its own receipt.",
        BROKEN_PARENT_RECEIPT_AS_CHILD_RECEIPTS,
        _expect_violation(
            "parent receipt copied into child slots fails",
            ("child_receipts_are_exact_current_owner_bound_and_distinct",),
        ),
    ),
    scenario(
        "every_declared_child_needs_one_receipt",
        "The receipt coverage set must equal the exact declared child-model set.",
        BROKEN_CHILD_RECEIPT_COVERAGE,
        _expect_violation(
            "missing child receipt coverage fails",
            ("child_receipts_are_exact_current_owner_bound_and_distinct",),
        ),
    ),
    scenario(
        "stale_child_receipt_cannot_reattach",
        "A child receipt must remain exact-current at the governed revision.",
        BROKEN_STALE_CHILD_RECEIPT,
        _expect_violation(
            "stale child receipt fails",
            ("child_receipts_are_exact_current_owner_bound_and_distinct",),
        ),
    ),
    scenario(
        "foreign_owner_child_receipt_cannot_reattach",
        "A receipt for another child or execution owner cannot fill the current child slot.",
        BROKEN_FOREIGN_CHILD_RECEIPT,
        _expect_violation(
            "foreign owner child receipt fails",
            ("child_receipts_are_exact_current_owner_bound_and_distinct",),
        ),
    ),
    scenario(
        "child_receipt_identities_must_be_distinct",
        "Two child evidence slots cannot share one receipt identity.",
        BROKEN_DUPLICATE_CHILD_RECEIPT,
        _expect_violation(
            "duplicate child receipt identity fails",
            ("child_receipts_are_exact_current_owner_bound_and_distinct",),
        ),
    ),
    scenario(
        "feedback_relation_classification_must_be_complete",
        "Feedback, retry, and repair relation kinds must all be classified into the bounded feedback graph.",
        BROKEN_INCOMPLETE_FEEDBACK_RELATION_CLASSIFICATION,
        _expect_violation(
            "incomplete feedback relation classification fails",
            ("feedback_loops_require_current_progress_contracts",),
        ),
    ),
    scenario(
        "feedback_loop_requires_progress_contract",
        "An explicit feedback SCC needs an explicit finite-progress contract.",
        BROKEN_MISSING_FEEDBACK_PROGRESS,
        _expect_violation(
            "missing feedback progress contract fails",
            ("feedback_loops_require_current_progress_contracts",),
        ),
    ),
    scenario(
        "retry_loop_requires_progress_contract",
        "A retry SCC needs an explicit finite-progress contract.",
        BROKEN_MISSING_RETRY_PROGRESS,
        _expect_violation(
            "missing retry progress contract fails",
            ("feedback_loops_require_current_progress_contracts",),
        ),
    ),
    scenario(
        "repair_loop_requires_progress_contract",
        "A repair SCC needs an explicit finite-progress contract.",
        BROKEN_MISSING_REPAIR_PROGRESS,
        _expect_violation(
            "missing repair progress contract fails",
            ("feedback_loops_require_current_progress_contracts",),
        ),
    ),
    scenario(
        "feedback_loop_rejects_stale_progress_evidence",
        "A declared feedback, retry, or repair progress contract remains unproved when its evidence is stale or missing.",
        BROKEN_STALE_FEEDBACK_PROGRESS,
        _expect_violation(
            "stale feedback progress evidence fails",
            ("feedback_loops_require_current_progress_contracts",),
        ),
    ),
    scenario(
        "feedback_loop_rejects_stale_progress_contract",
        "A feedback, retry, or repair contract from another topology revision cannot prove current progress.",
        BROKEN_STALE_FEEDBACK_PROGRESS_CONTRACT,
        _expect_violation(
            "stale feedback progress contract fails",
            ("feedback_loops_require_current_progress_contracts",),
        ),
    ),
    scenario(
        "checked_in_semantic_declaration_cannot_certify_child_currentness",
        "A semantic declaration describes topology but cannot certify its own child evidence.",
        BROKEN_DECLARATION_SELF_CERTIFIES_CHILD,
        _expect_violation(
            "self-certified child currentness fails",
            ("checked_in_declarations_cannot_self_certify_currentness",),
        ),
    ),
    scenario(
        "checked_in_semantic_declaration_cannot_certify_progress_currentness",
        "A progress declaration needs independently produced current evidence.",
        BROKEN_DECLARATION_SELF_CERTIFIES_PROGRESS,
        _expect_violation(
            "self-certified progress currentness fails",
            ("checked_in_declarations_cannot_self_certify_currentness",),
        ),
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
