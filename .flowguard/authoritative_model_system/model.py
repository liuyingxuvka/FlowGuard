"""Executable model for FlowGuard project model-system authority.

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard

Purpose: prove that observed, target, and experimental model systems remain
distinct; that one or many model changes activate atomically against a frozen
base; and that an observed-system rollback cannot move model authority before
the implementation and its effects are restored or compensated.

Modeled block shape: Input x State -> Set(Output x State).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from flowguard import (
    FunctionResult,
    Invariant,
    InvariantResult,
    Scenario,
    ScenarioExpectation,
    Workflow,
)
from flowguard.review import review_scenarios


@dataclass(frozen=True)
class AuthorityCase:
    name: str
    subject_lanes_distinct: bool = True
    one_observed_head: bool = True
    candidate_isolated: bool = True
    authority_derived_from_pointer: bool = True
    finite_coverage_boundary: bool = True
    coverage_set_equality: bool = True
    declared_materialized_model_sets_equal: bool = True
    diff_independently_derived: bool = True
    affected_closure_complete: bool = True
    affected_closure_is_fixed_point: bool = True
    aggregate_evidence_complete: bool = True
    evidence_coverage_union_exact: bool = True
    path_quality_changed_model_count: int = 1
    path_quality_current_model_count: int = 1
    path_quality_result_count: int = 1
    path_quality_changed_members_covered: bool = True
    path_quality_rows_belong_to_candidate_current_models: bool = True
    path_quality_rows_share_candidate_snapshot: bool = True
    path_quality_rows_exact_current_and_resolved: bool = True
    whole_self_qualification_requested: bool = False
    revision_builder_receipt_exact_current: bool = True
    revision_builder_native_owner_leaf_receipts_unique: bool = True
    revision_builder_native_owner_model_map_complete: bool = True
    revision_builder_full_parent_execution_bound: bool = True
    revision_builder_native_owner_independently_verified: bool = True
    revision_builder_one_frozen_child_observation: bool = True
    revision_builder_final_identity_freshness_passed: bool = True
    revision_builder_canonical_store_stable_through_publication: bool = True
    revision_builder_content_addressed_current: bool = True
    revision_builder_pointer_unchanged: bool = True
    expected_head_matches: bool = True
    full_head_compare_and_swap: bool = True
    lock_held_live_candidate_exact: bool = True
    final_live_resample_exact: bool = True
    immutable_records_before_pointer: bool = True
    pointer_changes_once: bool = True
    no_partial_member_activation: bool = True
    implementation_effects_restored: bool = True
    old_snapshot_revalidated: bool = True
    irreversible_effect_not_exact_rollback: bool = True
    rollback_is_reverse_revision: bool = True
    rollback_origin_head_matches: bool = True
    observed_subject_matches_software: bool = True
    instance_identity_is_local: bool = True
    global_revision_is_snapshot_only: bool = True
    incompatible_schema_has_one_direct_current_migration: bool = True
    unknown_impact_blocks: bool = True
    public_authority_closure_complete: bool = True
    maturation_task_and_coverage_are_frozen: bool = True
    maturation_prediction_and_falsifier_present: bool = True
    maturation_receipts_bind_exact_candidate: bool = True
    addressable_maturation_gap_keeps_iteration_open: bool = True
    maturation_terminal_reason_is_genuine: bool = True
    semantic_model_universe_exact: bool = True
    semantic_model_dispositions_complete: bool = True
    semantic_model_relations_complete: bool = True
    semantic_derivation_fingerprint_present: bool = True
    semantic_completion_evidence_terminal_verified: bool = True
    target_provider_registry_exact_current: bool = True
    target_snapshot_exact_current: bool = True
    target_provider_payload_matches_current_native_reports: bool = True
    broad_blueprint_claim_consumes_provider_lineage: bool = True
    semantic_mesh_identity_derived_from_topology: bool = True
    topology_runtime_evidence_exact_current: bool = True
    affected_semantic_relation_closure_complete: bool = True
    topology_root_sentinel_present: bool = True
    topology_root_sentinel_unique: bool = True
    topology_structural_parent_unique: bool = True
    topology_cross_boundary_support_non_structural: bool = True
    topology_parent_receipt_composition_only: bool = True
    topology_child_receipt_coverage_exact: bool = True
    topology_child_receipts_exact_current: bool = True
    topology_child_receipts_owner_bound: bool = True
    topology_child_receipts_distinct: bool = True
    topology_feedback_relation_classification_complete: bool = True
    topology_feedback_progress_contract_present: bool = True
    topology_retry_progress_contract_present: bool = True
    topology_repair_progress_contract_present: bool = True
    topology_feedback_progress_contract_exact_current: bool = True
    topology_feedback_progress_evidence_exact_current: bool = True
    topology_currentness_independent_of_checked_in_declaration: bool = True
    raw_manifest_route_has_no_blueprint_authority: bool = True
    project_document_carries_intent_inventory: bool = True
    canonical_export_preserves_all_blueprint_layers: bool = True
    export_status_is_distinct_from_model_readiness: bool = True
    intent_inventory_exact_current: bool = True
    intent_direct_source_fingerprints_exact_current: bool = True
    intent_work_context_identity_exact_current: bool = True
    intent_sources_stable_through_publication: bool = True
    intent_present_or_evidence_bound_no_intent: bool = True
    accepted_intent_effects_resolved: bool = True
    intent_conflicts_block_activation: bool = True
    cumulative_intent_view_inside_current_revision: bool = True
    prior_active_intent_transitions_complete: bool = True
    intent_identity_changes_use_explicit_supersession: bool = True
    active_intent_sources_all_reverified: bool = True
    active_direct_intent_sources_bound_to_logical_owner_inputs: bool = True
    current_model_owner_denominator_exact: bool = True
    current_model_owner_bindings_exact: bool = True
    legacy_intent_schema_has_no_current_fallback: bool = True


@dataclass(frozen=True)
class AuthorityState:
    case_name: str = ""
    subject_lanes_distinct: bool = False
    one_observed_head: bool = False
    candidate_isolated: bool = False
    authority_derived_from_pointer: bool = False
    finite_coverage_boundary: bool = False
    coverage_set_equality: bool = False
    declared_materialized_model_sets_equal: bool = False
    diff_independently_derived: bool = False
    affected_closure_complete: bool = False
    affected_closure_is_fixed_point: bool = False
    aggregate_evidence_complete: bool = False
    evidence_coverage_union_exact: bool = False
    path_quality_changed_model_count: int = 0
    path_quality_current_model_count: int = 0
    path_quality_result_count: int = 0
    path_quality_changed_members_covered: bool = False
    path_quality_rows_belong_to_candidate_current_models: bool = False
    path_quality_rows_share_candidate_snapshot: bool = False
    path_quality_rows_exact_current_and_resolved: bool = False
    whole_self_qualification_requested: bool = False
    revision_builder_receipt_exact_current: bool = False
    revision_builder_native_owner_leaf_receipts_unique: bool = False
    revision_builder_native_owner_model_map_complete: bool = False
    revision_builder_full_parent_execution_bound: bool = False
    revision_builder_native_owner_independently_verified: bool = False
    revision_builder_one_frozen_child_observation: bool = False
    revision_builder_final_identity_freshness_passed: bool = False
    revision_builder_canonical_store_stable_through_publication: bool = False
    revision_builder_content_addressed_current: bool = False
    revision_builder_pointer_unchanged: bool = False
    expected_head_matches: bool = False
    full_head_compare_and_swap: bool = False
    lock_held_live_candidate_exact: bool = False
    final_live_resample_exact: bool = False
    immutable_records_before_pointer: bool = False
    pointer_changes_once: bool = False
    no_partial_member_activation: bool = False
    implementation_effects_restored: bool = False
    old_snapshot_revalidated: bool = False
    irreversible_effect_not_exact_rollback: bool = False
    rollback_is_reverse_revision: bool = False
    rollback_origin_head_matches: bool = False
    observed_subject_matches_software: bool = False
    instance_identity_is_local: bool = False
    global_revision_is_snapshot_only: bool = False
    incompatible_schema_has_one_direct_current_migration: bool = False
    unknown_impact_blocks: bool = False
    public_authority_closure_complete: bool = False
    maturation_task_and_coverage_are_frozen: bool = False
    maturation_prediction_and_falsifier_present: bool = False
    maturation_receipts_bind_exact_candidate: bool = False
    addressable_maturation_gap_keeps_iteration_open: bool = False
    maturation_terminal_reason_is_genuine: bool = False
    semantic_model_universe_exact: bool = False
    semantic_model_dispositions_complete: bool = False
    semantic_model_relations_complete: bool = False
    semantic_derivation_fingerprint_present: bool = False
    semantic_completion_evidence_terminal_verified: bool = False
    target_provider_registry_exact_current: bool = False
    target_snapshot_exact_current: bool = False
    target_provider_payload_matches_current_native_reports: bool = False
    broad_blueprint_claim_consumes_provider_lineage: bool = False
    semantic_mesh_identity_derived_from_topology: bool = False
    topology_runtime_evidence_exact_current: bool = False
    affected_semantic_relation_closure_complete: bool = False
    topology_root_sentinel_present: bool = False
    topology_root_sentinel_unique: bool = False
    topology_structural_parent_unique: bool = False
    topology_cross_boundary_support_non_structural: bool = False
    topology_parent_receipt_composition_only: bool = False
    topology_child_receipt_coverage_exact: bool = False
    topology_child_receipts_exact_current: bool = False
    topology_child_receipts_owner_bound: bool = False
    topology_child_receipts_distinct: bool = False
    topology_feedback_relation_classification_complete: bool = False
    topology_feedback_progress_contract_present: bool = False
    topology_retry_progress_contract_present: bool = False
    topology_repair_progress_contract_present: bool = False
    topology_feedback_progress_contract_exact_current: bool = False
    topology_feedback_progress_evidence_exact_current: bool = False
    topology_currentness_independent_of_checked_in_declaration: bool = False
    raw_manifest_route_has_no_blueprint_authority: bool = False
    project_document_carries_intent_inventory: bool = False
    canonical_export_preserves_all_blueprint_layers: bool = False
    export_status_is_distinct_from_model_readiness: bool = False
    intent_inventory_exact_current: bool = False
    intent_direct_source_fingerprints_exact_current: bool = False
    intent_work_context_identity_exact_current: bool = False
    intent_sources_stable_through_publication: bool = False
    intent_present_or_evidence_bound_no_intent: bool = False
    accepted_intent_effects_resolved: bool = False
    intent_conflicts_block_activation: bool = False
    cumulative_intent_view_inside_current_revision: bool = False
    prior_active_intent_transitions_complete: bool = False
    intent_identity_changes_use_explicit_supersession: bool = False
    active_intent_sources_all_reverified: bool = False
    active_direct_intent_sources_bound_to_logical_owner_inputs: bool = False
    current_model_owner_denominator_exact: bool = False
    current_model_owner_bindings_exact: bool = False
    legacy_intent_schema_has_no_current_fallback: bool = False


class EvaluateAuthorityRevision:
    name = "EvaluateAuthorityRevision"
    reads = ("AuthorityState",)
    writes = tuple(AuthorityState.__dataclass_fields__)
    accepted_input_type = AuthorityCase
    input_description = "project model-system authority revision case"
    output_description = "evaluated authority and rollback state"
    idempotency = "same frozen case produces the same authority state"

    def apply(self, input_obj: AuthorityCase, _state: AuthorityState):
        values = {"case_name": input_obj.name}
        values.update(
            {
                field_name: getattr(input_obj, field_name)
                for field_name in AuthorityState.__dataclass_fields__
                if field_name != "case_name"
            }
        )
        state = AuthorityState(**values)
        return (
            FunctionResult(
                output=input_obj,
                new_state=state,
                label=input_obj.name,
                reason="projected revision, activation, and rollback gates",
            ),
        )


def _pass() -> InvariantResult:
    return InvariantResult.pass_()


def _fail(name: str, message: str) -> InvariantResult:
    return InvariantResult.fail(message, {"violation": name})


def lanes_and_head_are_unambiguous(
    state: AuthorityState, _trace: object
) -> InvariantResult:
    if not state.case_name:
        return _pass()
    if not state.subject_lanes_distinct:
        return _fail(
            "lanes_and_head_are_unambiguous",
            "observed, target, and experiment subjects are conflated",
        )
    if not state.one_observed_head:
        return _fail(
            "lanes_and_head_are_unambiguous",
            "project has zero or multiple observed implementation heads",
        )
    if not state.authority_derived_from_pointer:
        return _fail(
            "lanes_and_head_are_unambiguous",
            "current authority is inferred from a mutable label or discovery",
        )
    return _pass()


def candidates_never_mutate_observed_authority(
    state: AuthorityState, _trace: object
) -> InvariantResult:
    if not state.case_name:
        return _pass()
    if not state.candidate_isolated:
        return _fail(
            "candidates_never_mutate_observed_authority",
            "candidate construction changed the observed head",
        )
    return _pass()


def coverage_claim_is_finite_set_equality(
    state: AuthorityState, _trace: object
) -> InvariantResult:
    if not state.case_name:
        return _pass()
    if not state.finite_coverage_boundary:
        return _fail(
            "coverage_claim_is_finite_set_equality",
            "coverage claim has no finite fingerprinted universe",
        )
    if not state.coverage_set_equality:
        return _fail(
            "coverage_claim_is_finite_set_equality",
            "required and covered ids are not equal in every dimension",
        )
    if not state.declared_materialized_model_sets_equal:
        return _fail(
            "coverage_claim_is_finite_set_equality",
            "declared non-excluded models differ from materialized model-and-runner ids",
        )
    return _pass()


def revision_set_closes_as_one_unit(
    state: AuthorityState, _trace: object
) -> InvariantResult:
    if not state.case_name:
        return _pass()
    if not state.affected_closure_complete:
        return _fail(
            "revision_set_closes_as_one_unit",
            "affected parent, sibling, relation, commitment, field, contract, or test is missing",
        )
    if not state.diff_independently_derived:
        return _fail(
            "revision_set_closes_as_one_unit",
            "caller declarations replaced or narrowed the canonical snapshot diff",
        )
    if not state.affected_closure_is_fixed_point:
        return _fail(
            "revision_set_closes_as_one_unit",
            "affected ids are not the fixed point of the typed base and candidate relations",
        )
    if not state.aggregate_evidence_complete:
        return _fail(
            "revision_set_closes_as_one_unit",
            "required revision-set evidence is failed, stale, skipped, or not run",
        )
    if not state.evidence_coverage_union_exact:
        return _fail(
            "revision_set_closes_as_one_unit",
            "passing receipts do not cover the complete affected identity set exactly",
        )
    if not state.no_partial_member_activation:
        return _fail(
            "revision_set_closes_as_one_unit",
            "one revision-set member activated independently",
        )
    return _pass()


def path_quality_denominators_are_distinct_and_current(
    state: AuthorityState, _trace: object
) -> InvariantResult:
    if not state.case_name:
        return _pass()
    if state.path_quality_changed_model_count < 1:
        return _fail(
            "path_quality_denominators_are_distinct_and_current",
            "the revision has no non-empty independently derived add-or-replace model denominator",
        )
    if state.path_quality_current_model_count < state.path_quality_changed_model_count:
        return _fail(
            "path_quality_denominators_are_distinct_and_current",
            "the candidate current-model denominator is smaller than its changed-model denominator",
        )
    if not state.path_quality_changed_members_covered:
        return _fail(
            "path_quality_denominators_are_distinct_and_current",
            "one or more added or replaced models lack a candidate path-quality row",
        )
    if state.path_quality_result_count < state.path_quality_changed_model_count:
        return _fail(
            "path_quality_denominators_are_distinct_and_current",
            "path-quality results do not cover the complete minimum changed-model denominator",
        )
    if state.path_quality_result_count > state.path_quality_current_model_count:
        return _fail(
            "path_quality_denominators_are_distinct_and_current",
            "path-quality results exceed the candidate current-model denominator",
        )
    if (
        state.whole_self_qualification_requested
        and state.path_quality_result_count
        != state.path_quality_current_model_count
    ):
        return _fail(
            "path_quality_denominators_are_distinct_and_current",
            "whole-self qualification does not cover the complete current-model denominator",
        )
    if not state.path_quality_rows_belong_to_candidate_current_models:
        return _fail(
            "path_quality_denominators_are_distinct_and_current",
            "a path-quality row names a foreign or non-current model outside the candidate denominator",
        )
    if not state.path_quality_rows_share_candidate_snapshot:
        return _fail(
            "path_quality_denominators_are_distinct_and_current",
            "a path-quality row belongs to a different candidate snapshot",
        )
    if not state.path_quality_rows_exact_current_and_resolved:
        return _fail(
            "path_quality_denominators_are_distinct_and_current",
            "a supplied path-quality row is stale, unvalidated, or unresolved",
        )
    return _pass()


def revision_generation_is_current_and_pointer_free(
    state: AuthorityState, _trace: object
) -> InvariantResult:
    if not state.case_name:
        return _pass()
    if not state.revision_builder_receipt_exact_current:
        return _fail(
            "revision_generation_is_current_and_pointer_free",
            "revision generation accepted stale, scoped, incomplete, or foreign parent evidence",
        )
    if not state.revision_builder_native_owner_leaf_receipts_unique:
        return _fail(
            "revision_generation_is_current_and_pointer_free",
            "revision generation copied one parent receipt into several native-owner evidence leaves",
        )
    if not state.revision_builder_native_owner_model_map_complete:
        return _fail(
            "revision_generation_is_current_and_pointer_free",
            "an affected or candidate-reachable native owner route has no unique explicit semantic model binding",
        )
    if not state.revision_builder_full_parent_execution_bound:
        return _fail(
            "revision_generation_is_current_and_pointer_free",
            "revision generation accepted a relabeled parent wrapper without a canonical full-selection composition receipt",
        )
    if not state.revision_builder_native_owner_independently_verified:
        return _fail(
            "revision_generation_is_current_and_pointer_free",
            "revision generation trusted caller-declared native-owner verification instead of reloading the canonical receipt and deriving current verification",
        )
    if not state.revision_builder_one_frozen_child_observation:
        return _fail(
            "revision_generation_is_current_and_pointer_free",
            "revision generation rebuilt the same complete model-child closure independently for each native owner",
        )
    if not state.revision_builder_final_identity_freshness_passed:
        return _fail(
            "revision_generation_is_current_and_pointer_free",
            "revision generation omitted or failed its final source, environment, parent, child, and aggregate identity comparison",
        )
    if not state.revision_builder_canonical_store_stable_through_publication:
        return _fail(
            "revision_generation_is_current_and_pointer_free",
            "revision generation retained an in-memory pass after canonical aggregate or child evidence disappeared",
        )
    if not state.revision_builder_content_addressed_current:
        return _fail(
            "revision_generation_is_current_and_pointer_free",
            "revision generation emitted a non-current or non-content-addressed artifact",
        )
    if not state.revision_builder_pointer_unchanged:
        return _fail(
            "revision_generation_is_current_and_pointer_free",
            "revision generation changed observed authority without the activation owner",
        )
    return _pass()


def activation_is_compare_and_swap_pointer_last(
    state: AuthorityState, _trace: object
) -> InvariantResult:
    if not state.case_name:
        return _pass()
    if not state.expected_head_matches:
        return _fail(
            "activation_is_compare_and_swap_pointer_last",
            "observed head drifted after candidate construction",
        )
    if not state.full_head_compare_and_swap:
        return _fail(
            "activation_is_compare_and_swap_pointer_last",
            "activation compared only a snapshot or partial head identity",
        )
    if not state.lock_held_live_candidate_exact:
        return _fail(
            "activation_is_compare_and_swap_pointer_last",
            "lock-held live candidate materialization differs from the accepted candidate",
        )
    if not state.final_live_resample_exact:
        return _fail(
            "activation_is_compare_and_swap_pointer_last",
            "governed live input drifted before the pointer write",
        )
    if not state.immutable_records_before_pointer:
        return _fail(
            "activation_is_compare_and_swap_pointer_last",
            "candidate, decision, or activation evidence was not persisted first",
        )
    if not state.pointer_changes_once:
        return _fail(
            "activation_is_compare_and_swap_pointer_last",
            "activation exposed a partial or repeated current-head transition",
        )
    return _pass()


def observed_head_matches_real_software(
    state: AuthorityState, _trace: object
) -> InvariantResult:
    if not state.case_name:
        return _pass()
    if not state.observed_subject_matches_software:
        return _fail(
            "observed_head_matches_real_software",
            "observed snapshot does not describe the implemented software revision",
        )
    return _pass()


def local_identity_and_global_provenance_are_separate(
    state: AuthorityState, _trace: object
) -> InvariantResult:
    if not state.case_name:
        return _pass()
    if not state.instance_identity_is_local:
        return _fail(
            "local_identity_and_global_provenance_are_separate",
            "one global source revision was copied into every model instance identity",
        )
    if not state.global_revision_is_snapshot_only:
        return _fail(
            "local_identity_and_global_provenance_are_separate",
            "global source or Git revision escaped snapshot provenance",
        )
    return _pass()


def impact_and_public_closure_fail_closed(
    state: AuthorityState, _trace: object
) -> InvariantResult:
    if not state.case_name:
        return _pass()
    if not state.unknown_impact_blocks:
        return _fail(
            "impact_and_public_closure_fail_closed",
            "unknown model impact silently expanded to run-all",
        )
    if not state.public_authority_closure_complete:
        return _fail(
            "impact_and_public_closure_fail_closed",
            "release tree omits the current authority snapshot, revision, or activation record",
        )
    return _pass()


def incompatible_authority_schema_has_no_dual_reader(
    state: AuthorityState, _trace: object
) -> InvariantResult:
    if not state.case_name:
        return _pass()
    if not state.incompatible_schema_has_one_direct_current_migration:
        return _fail(
            "incompatible_authority_schema_has_no_dual_reader",
            "an incompatible authority schema remained readable beside the current schema",
        )
    return _pass()


def maturation_proves_behavior_instead_of_accepting_self_report(
    state: AuthorityState, _trace: object
) -> InvariantResult:
    if not state.case_name:
        return _pass()
    if not state.maturation_task_and_coverage_are_frozen:
        return _fail(
            "maturation_proves_behavior_instead_of_accepting_self_report",
            "model maturation can close without a task-bound independent coverage universe",
        )
    if not state.maturation_prediction_and_falsifier_present:
        return _fail(
            "maturation_proves_behavior_instead_of_accepting_self_report",
            "a model-understanding claim lacks a prediction and falsifier",
        )
    if not state.maturation_receipts_bind_exact_candidate:
        return _fail(
            "maturation_proves_behavior_instead_of_accepting_self_report",
            "caller resolution or a foreign receipt can close the candidate",
        )
    if not state.addressable_maturation_gap_keeps_iteration_open:
        return _fail(
            "maturation_proves_behavior_instead_of_accepting_self_report",
            "an addressable gap can be scoped away or treated as terminal",
        )
    if not state.maturation_terminal_reason_is_genuine:
        return _fail(
            "maturation_proves_behavior_instead_of_accepting_self_report",
            "upgrade-required was mislabeled as a terminal maturation result",
        )
    return _pass()


def whole_system_understanding_is_semantic_and_current(
    state: AuthorityState, _trace: object
) -> InvariantResult:
    if not state.case_name:
        return _pass()
    if not state.semantic_model_universe_exact:
        return _fail(
            "whole_system_understanding_is_semantic_and_current",
            "a partial model slice was promoted to whole-system understanding",
        )
    if not state.semantic_model_dispositions_complete:
        return _fail(
            "whole_system_understanding_is_semantic_and_current",
            "inventory presence replaced per-model semantic disposition and rationale",
        )
    if not state.semantic_model_relations_complete:
        return _fail(
            "whole_system_understanding_is_semantic_and_current",
            "the semantic mesh lacks a parent or consumer relation",
        )
    if not state.semantic_derivation_fingerprint_present:
        return _fail(
            "whole_system_understanding_is_semantic_and_current",
            "the semantic universe has no content-addressed derivation base",
        )
    if not state.semantic_completion_evidence_terminal_verified:
        return _fail(
            "whole_system_understanding_is_semantic_and_current",
            "a candidate or unverified artifact was treated as whole-system completion evidence",
        )
    if not state.target_provider_registry_exact_current:
        return _fail(
            "whole_system_understanding_is_semantic_and_current",
            "target-system provider identities and capabilities are not frozen in one current registry",
        )
    if not state.target_snapshot_exact_current:
        return _fail(
            "whole_system_understanding_is_semantic_and_current",
            "target-system descriptor and provider results do not match one current snapshot",
        )
    if not state.target_provider_payload_matches_current_native_reports:
        return _fail(
            "whole_system_understanding_is_semantic_and_current",
            "frozen provider payloads differ from the current native project reports",
        )
    if not state.broad_blueprint_claim_consumes_provider_lineage:
        return _fail(
            "whole_system_understanding_is_semantic_and_current",
            "a broad static-blueprint claim omits its provider registry or snapshot lineage",
        )
    if not state.semantic_mesh_identity_derived_from_topology:
        return _fail(
            "whole_system_understanding_is_semantic_and_current",
            "semantic mesh identity is caller-declared instead of derived from the reviewed topology",
        )
    if not state.topology_runtime_evidence_exact_current:
        return _fail(
            "whole_system_understanding_is_semantic_and_current",
            "topology consumes missing, stale, foreign, or cross-revision runtime evidence",
        )
    if not state.affected_semantic_relation_closure_complete:
        return _fail(
            "whole_system_understanding_is_semantic_and_current",
            "affected understanding omits a producer, consumer, delegation, or support dependency",
        )
    if not state.raw_manifest_route_has_no_blueprint_authority:
        return _fail(
            "whole_system_understanding_is_semantic_and_current",
            "a raw manifest/current-label comparison remains an alternate blueprint authority",
        )
    if not state.project_document_carries_intent_inventory:
        return _fail(
            "whole_system_understanding_is_semantic_and_current",
            "the strict project document omits the intent inventory used by readiness",
        )
    if not state.canonical_export_preserves_all_blueprint_layers:
        return _fail(
            "whole_system_understanding_is_semantic_and_current",
            "the portable project export omits a canonical blueprint layer",
        )
    if not state.export_status_is_distinct_from_model_readiness:
        return _fail(
            "whole_system_understanding_is_semantic_and_current",
            "successful materialization is being reported as complete model understanding",
        )
    return _pass()


def topology_authority_is_typed_current_and_independently_evidenced(
    state: AuthorityState, _trace: object
) -> InvariantResult:
    if not state.case_name:
        return _pass()
    if not state.topology_root_sentinel_present:
        return _fail(
            "topology_authority_is_typed_current_and_independently_evidenced",
            "the authoritative topology has no node that declares the root sentinel",
        )
    if not state.topology_root_sentinel_unique:
        return _fail(
            "topology_authority_is_typed_current_and_independently_evidenced",
            "more than one authoritative topology node declares the root sentinel",
        )
    if not state.topology_structural_parent_unique:
        return _fail(
            "topology_authority_is_typed_current_and_independently_evidenced",
            "one child model has more than one structural parent",
        )
    if not state.topology_cross_boundary_support_non_structural:
        return _fail(
            "topology_authority_is_typed_current_and_independently_evidenced",
            "cross-boundary support is being counted as another structural parent",
        )
    if not state.topology_parent_receipt_composition_only:
        return _fail(
            "topology_authority_is_typed_current_and_independently_evidenced",
            "a full parent receipt is being promoted from composition evidence to child evidence",
        )
    if not state.topology_child_receipt_coverage_exact:
        return _fail(
            "topology_authority_is_typed_current_and_independently_evidenced",
            "the current declared child-model set is not covered exactly by child receipts",
        )
    if not state.topology_child_receipts_exact_current:
        return _fail(
            "topology_authority_is_typed_current_and_independently_evidenced",
            "a child evidence slot contains missing, stale, scoped, foreign-revision, or non-terminal evidence",
        )
    if not state.topology_child_receipts_owner_bound:
        return _fail(
            "topology_authority_is_typed_current_and_independently_evidenced",
            "a child receipt does not bind its exact child model and execution owner",
        )
    if not state.topology_child_receipts_distinct:
        return _fail(
            "topology_authority_is_typed_current_and_independently_evidenced",
            "one receipt identity is reused by more than one child-model evidence slot",
        )
    if not state.topology_feedback_relation_classification_complete:
        return _fail(
            "topology_authority_is_typed_current_and_independently_evidenced",
            "feedback, retry, and repair relations are not completely classified into the bounded feedback graph",
        )
    if not state.topology_feedback_progress_contract_present:
        return _fail(
            "topology_authority_is_typed_current_and_independently_evidenced",
            "an explicit feedback SCC has no finite progress contract",
        )
    if not state.topology_retry_progress_contract_present:
        return _fail(
            "topology_authority_is_typed_current_and_independently_evidenced",
            "a retry SCC has no finite progress contract",
        )
    if not state.topology_repair_progress_contract_present:
        return _fail(
            "topology_authority_is_typed_current_and_independently_evidenced",
            "a repair SCC has no finite progress contract",
        )
    if not state.topology_feedback_progress_contract_exact_current:
        return _fail(
            "topology_authority_is_typed_current_and_independently_evidenced",
            "a typed feedback, retry, or repair SCC uses a stale, foreign, or cross-revision progress contract",
        )
    if not state.topology_feedback_progress_evidence_exact_current:
        return _fail(
            "topology_authority_is_typed_current_and_independently_evidenced",
            "a typed feedback, retry, or repair SCC has missing, stale, foreign, or progress-only progress evidence",
        )
    if not state.topology_currentness_independent_of_checked_in_declaration:
        return _fail(
            "topology_authority_is_typed_current_and_independently_evidenced",
            "a checked-in semantic declaration is being accepted as proof of its own child or progress currentness",
        )
    return _pass()


def revision_intent_lineage_is_exact_and_resolved(
    state: AuthorityState, _trace: object
) -> InvariantResult:
    if not state.case_name:
        return _pass()
    if not state.intent_inventory_exact_current:
        return _fail(
            "revision_intent_lineage_is_exact_and_resolved",
            "revision lineage omits or accepts stale declared intent contributions",
        )
    if not state.intent_direct_source_fingerprints_exact_current:
        return _fail(
            "revision_intent_lineage_is_exact_and_resolved",
            "a direct project intent source no longer matches its frozen canonical fingerprint",
        )
    if not state.intent_work_context_identity_exact_current:
        return _fail(
            "revision_intent_lineage_is_exact_and_resolved",
            "a WorkContext intent source does not match its declared current context, native owner, source reference, and artifact identity",
        )
    if not state.intent_sources_stable_through_publication:
        return _fail(
            "revision_intent_lineage_is_exact_and_resolved",
            "an intent source identity changed after the revision build froze it and before publication",
        )
    if not state.intent_present_or_evidence_bound_no_intent:
        return _fail(
            "revision_intent_lineage_is_exact_and_resolved",
            "an empty revision intent inventory passed without an evidence-bound no-intent rationale",
        )
    if not state.accepted_intent_effects_resolved:
        return _fail(
            "revision_intent_lineage_is_exact_and_resolved",
            "an accepted intent contribution has no changed model identity or explicit gap disposition",
        )
    if not state.intent_conflicts_block_activation:
        return _fail(
            "revision_intent_lineage_is_exact_and_resolved",
            "conflicting accepted intent contributions do not block activation",
        )
    if not state.cumulative_intent_view_inside_current_revision:
        return _fail(
            "revision_intent_lineage_is_exact_and_resolved",
            "the latest revision delta is being treated as whole-system current intent or a second current-intent pointer exists",
        )
    if not state.prior_active_intent_transitions_complete:
        return _fail(
            "revision_intent_lineage_is_exact_and_resolved",
            "a prior active intent contribution disappeared without an explicit retain, supersede, or retire transition",
        )
    if not state.intent_identity_changes_use_explicit_supersession:
        return _fail(
            "revision_intent_lineage_is_exact_and_resolved",
            "a contribution id changed content through implicit last-write-wins instead of a new id and exact supersession",
        )
    if not state.active_intent_sources_all_reverified:
        return _fail(
            "revision_intent_lineage_is_exact_and_resolved",
            "revision construction reverified only the new delta and left a stale active cumulative intent source",
        )
    if not state.active_direct_intent_sources_bound_to_logical_owner_inputs:
        return _fail(
            "revision_intent_lineage_is_exact_and_resolved",
            "an active direct intent source is detached from its exact logical owner model input identity",
        )
    if not state.current_model_owner_denominator_exact:
        return _fail(
            "revision_intent_lineage_is_exact_and_resolved",
            "intent contributions or bindings shrank or invented the independently derived current model-owner denominator",
        )
    if not state.current_model_owner_bindings_exact:
        return _fail(
            "revision_intent_lineage_is_exact_and_resolved",
            "a current model owner lacks one exact effective intent and model-realizes-purpose binding or uses a root fallback",
        )
    if not state.legacy_intent_schema_has_no_current_fallback:
        return _fail(
            "revision_intent_lineage_is_exact_and_resolved",
            "normal current authority fell back to a legacy revision or reconstructed cumulative intent from historical deltas",
        )
    return _pass()


def rollback_restores_reality_before_authority(
    state: AuthorityState, _trace: object
) -> InvariantResult:
    if not state.case_name:
        return _pass()
    if not state.implementation_effects_restored:
        return _fail(
            "rollback_restores_reality_before_authority",
            "code, configuration, data, or external effects were not restored or compensated",
        )
    if not state.old_snapshot_revalidated:
        return _fail(
            "rollback_restores_reality_before_authority",
            "old observed snapshot was not revalidated after implementation restoration",
        )
    if not state.irreversible_effect_not_exact_rollback:
        return _fail(
            "rollback_restores_reality_before_authority",
            "irreversible effects were mislabeled as exact rollback",
        )
    if not state.rollback_is_reverse_revision:
        return _fail(
            "rollback_restores_reality_before_authority",
            "rollback receipt was used as revision identity instead of a reverse revision set",
        )
    if not state.rollback_origin_head_matches:
        return _fail(
            "rollback_restores_reality_before_authority",
            "rollback contract matches a snapshot but not the complete originating head",
        )
    return _pass()


INVARIANTS = (
    Invariant(
        "lanes_and_head_are_unambiguous",
        "Observed, target, and experiment lanes are distinct and one pointer owns current authority.",
        lanes_and_head_are_unambiguous,
    ),
    Invariant(
        "candidates_never_mutate_observed_authority",
        "Candidate construction cannot mutate the observed implementation head.",
        candidates_never_mutate_observed_authority,
    ),
    Invariant(
        "coverage_claim_is_finite_set_equality",
        "Complete coverage is set equality within a finite fingerprinted boundary.",
        coverage_claim_is_finite_set_equality,
    ),
    Invariant(
        "revision_set_closes_as_one_unit",
        "All affected revision members and evidence close or none activates.",
        revision_set_closes_as_one_unit,
    ),
    Invariant(
        "path_quality_denominators_are_distinct_and_current",
        "Added or replaced models form the ordinary minimum path-quality denominator; an explicit whole-self qualification requires the complete current-model denominator while an ordinary exact-current candidate may carry any verified subset through that boundary.",
        path_quality_denominators_are_distinct_and_current,
    ),
    Invariant(
        "revision_generation_is_current_and_pointer_free",
        "Revision generation consumes exact-current evidence and cannot activate authority.",
        revision_generation_is_current_and_pointer_free,
    ),
    Invariant(
        "activation_is_compare_and_swap_pointer_last",
        "Activation validates the expected head and writes the pointer last once.",
        activation_is_compare_and_swap_pointer_last,
    ),
    Invariant(
        "observed_head_matches_real_software",
        "The observed snapshot identifies the real implemented software revision.",
        observed_head_matches_real_software,
    ),
    Invariant(
        "local_identity_and_global_provenance_are_separate",
        "Model instances use local content identity while global revisions remain snapshot provenance.",
        local_identity_and_global_provenance_are_separate,
    ),
    Invariant(
        "impact_and_public_closure_fail_closed",
        "Unknown impact and missing public authority records block instead of falling back.",
        impact_and_public_closure_fail_closed,
    ),
    Invariant(
        "incompatible_authority_schema_has_no_dual_reader",
        "An incompatible authority schema is replaced directly and never remains as a second reader.",
        incompatible_authority_schema_has_no_dual_reader,
    ),
    Invariant(
        "maturation_proves_behavior_instead_of_accepting_self_report",
        "Task-local maturation closes only from predictions, falsifiers, exact receipts, and genuine terminal reasons.",
        maturation_proves_behavior_instead_of_accepting_self_report,
    ),
    Invariant(
        "whole_system_understanding_is_semantic_and_current",
        "Whole-system understanding requires the exact universe, semantic dispositions and relations, derivation identity, and current terminal evidence.",
        whole_system_understanding_is_semantic_and_current,
    ),
    Invariant(
        "topology_authority_is_typed_current_and_independently_evidenced",
        "Topology authority has exactly one root sentinel, one structural parent per child, complete feedback relation classification, exact independent child receipts, and current feedback, retry, and repair progress evidence.",
        topology_authority_is_typed_current_and_independently_evidenced,
    ),
    Invariant(
        "revision_intent_lineage_is_exact_and_resolved",
        "Revision lineage consumes one exact intent inventory and blocks unresolved or conflicting accepted effects.",
        revision_intent_lineage_is_exact_and_resolved,
    ),
    Invariant(
        "rollback_restores_reality_before_authority",
        "Operational rollback restores or compensates reality and revalidates it before moving authority.",
        rollback_restores_reality_before_authority,
    ),
)


def _expect_ok(summary: str) -> ScenarioExpectation:
    return ScenarioExpectation(
        expected_status="ok",
        required_trace_labels=("complete_authority_transaction",),
        summary=summary,
    )


def _expect_violation(name: str, summary: str) -> ScenarioExpectation:
    return ScenarioExpectation(
        expected_status="violation",
        expected_violation_names=(name,),
        summary=summary,
    )


def _scenario(
    name: str,
    description: str,
    case: AuthorityCase,
    expected: ScenarioExpectation,
) -> Scenario:
    return Scenario(
        name=name,
        description=description,
        workflow=Workflow(
            (EvaluateAuthorityRevision(),),
            name="authoritative_model_system_revision",
        ),
        initial_state=AuthorityState(),
        external_input_sequence=(case,),
        invariants=INVARIANTS,
        expected=expected,
    )


GOOD = AuthorityCase("complete_authority_transaction")
SCENARIOS = (
    _scenario(
        "complete_transaction_passes",
        "A bounded, evidence-complete multi-model activation and return path passes.",
        GOOD,
        _expect_ok("complete model-system transaction passes"),
    ),
    _scenario(
        "incremental_revision_may_carry_complete_current_path_quality_dna",
        "An incremental revision with five added or replaced models may carry exact-current path-quality rows for all 51 models in the same candidate snapshot; the minimum changed denominator is not an exact result-set ceiling.",
        AuthorityCase(
            "complete_authority_transaction",
            path_quality_changed_model_count=5,
            path_quality_current_model_count=51,
            path_quality_result_count=51,
        ),
        _expect_ok("complete current path-quality DNA is accepted for an incremental revision"),
    ),
    _scenario(
        "whole_self_qualification_requires_complete_current_path_quality_dna",
        "When the caller explicitly requests whole-self qualification, all 51 current models must carry exact-current path-quality rows under the same candidate snapshot.",
        AuthorityCase(
            "complete_authority_transaction",
            path_quality_changed_model_count=1,
            path_quality_current_model_count=51,
            path_quality_result_count=51,
            whole_self_qualification_requested=True,
        ),
        _expect_ok("complete current path-quality DNA closes whole-self qualification"),
    ),
    _scenario(
        "whole_self_qualification_rejects_affected_only_path_quality",
        "Changed-model coverage is sufficient for an ordinary revision but cannot stand in for the complete denominator when whole-self qualification is explicitly requested.",
        AuthorityCase(
            "whole_self_qualification_partial_path_quality",
            path_quality_changed_model_count=1,
            path_quality_current_model_count=51,
            path_quality_result_count=1,
            whole_self_qualification_requested=True,
        ),
        _expect_violation(
            "path_quality_denominators_are_distinct_and_current",
            "affected-only path quality cannot close whole-self qualification",
        ),
    ),
    _scenario(
        "every_changed_model_requires_path_quality_coverage",
        "The independently derived add-or-replace denominator remains the non-negotiable minimum even when optional unchanged current-model rows are allowed.",
        AuthorityCase(
            "changed_model_missing_path_quality_row",
            path_quality_changed_model_count=5,
            path_quality_current_model_count=51,
            path_quality_result_count=50,
            path_quality_changed_members_covered=False,
        ),
        _expect_violation(
            "path_quality_denominators_are_distinct_and_current",
            "missing changed-model path-quality row is rejected",
        ),
    ),
    _scenario(
        "foreign_extra_path_quality_row_blocks_revision",
        "A result beyond the minimum changed denominator cannot enter the candidate merely because every changed model is already covered.",
        AuthorityCase(
            "foreign_extra_path_quality_row",
            path_quality_changed_model_count=5,
            path_quality_current_model_count=51,
            path_quality_result_count=51,
            path_quality_rows_belong_to_candidate_current_models=False,
        ),
        _expect_violation(
            "path_quality_denominators_are_distinct_and_current",
            "foreign extra path-quality row is rejected",
        ),
    ),
    _scenario(
        "stale_or_unresolved_extra_path_quality_row_blocks_revision",
        "Every supplied row, including a current-DNA row beyond the minimum changed denominator, must remain validated, resolved, and current to the same candidate snapshot.",
        AuthorityCase(
            "stale_or_unresolved_extra_path_quality_row",
            path_quality_changed_model_count=5,
            path_quality_current_model_count=51,
            path_quality_result_count=51,
            path_quality_rows_exact_current_and_resolved=False,
        ),
        _expect_violation(
            "path_quality_denominators_are_distinct_and_current",
            "stale or unresolved extra path-quality row is rejected",
        ),
    ),
    _scenario(
        "cross_snapshot_extra_path_quality_row_blocks_revision",
        "Every optional current-DNA row must be frozen under the same candidate snapshot as the changed-model rows.",
        AuthorityCase(
            "cross_snapshot_extra_path_quality_row",
            path_quality_changed_model_count=5,
            path_quality_current_model_count=51,
            path_quality_result_count=51,
            path_quality_rows_share_candidate_snapshot=False,
        ),
        _expect_violation(
            "path_quality_denominators_are_distinct_and_current",
            "cross-snapshot extra path-quality row is rejected",
        ),
    ),
    _scenario(
        "current_typed_topology_evidence_passes",
        "One root sentinel, one structural parent per declared child, complete feedback classification, one distinct owner-bound receipt per declared child, and current feedback, retry, and repair progress evidence pass together.",
        AuthorityCase("complete_authority_transaction"),
        _expect_ok("typed current topology evidence passes"),
    ),
    _scenario(
        "target_cannot_be_current_by_label",
        "A mutable current label cannot make a target authoritative.",
        AuthorityCase(
            "target_current_by_label",
            authority_derived_from_pointer=False,
        ),
        _expect_violation(
            "lanes_and_head_are_unambiguous",
            "mutable current label is rejected",
        ),
    ),
    _scenario(
        "stale_intent_inventory_blocks_revision",
        "A revision cannot activate from an incomplete or stale intent-contribution inventory.",
        AuthorityCase(
            "stale_intent_inventory",
            intent_inventory_exact_current=False,
        ),
        _expect_violation(
            "revision_intent_lineage_is_exact_and_resolved",
            "stale intent inventory is rejected",
        ),
    ),
    _scenario(
        "direct_intent_source_fingerprint_must_be_current",
        "A direct project intent file must still match the exact canonical fingerprint frozen by its contribution.",
        AuthorityCase(
            "direct_intent_source_fingerprint_stale",
            intent_direct_source_fingerprints_exact_current=False,
        ),
        _expect_violation(
            "revision_intent_lineage_is_exact_and_resolved",
            "stale direct intent-source fingerprint is rejected",
        ),
    ),
    _scenario(
        "work_context_intent_source_requires_exact_current_identity",
        "A WorkContext-backed intent contribution must match the current declared context, native owner, source reference, and artifact fingerprint.",
        AuthorityCase(
            "work_context_intent_source_identity_mismatch",
            intent_work_context_identity_exact_current=False,
        ),
        _expect_violation(
            "revision_intent_lineage_is_exact_and_resolved",
            "mismatched WorkContext intent-source identity is rejected",
        ),
    ),
    _scenario(
        "intent_source_cannot_change_during_revision_build",
        "Every frozen direct-file or WorkContext intent source is rechecked and must retain the same identity through revision publication.",
        AuthorityCase(
            "intent_source_changes_during_revision_build",
            intent_sources_stable_through_publication=False,
        ),
        _expect_violation(
            "revision_intent_lineage_is_exact_and_resolved",
            "intent-source drift during revision build is rejected",
        ),
    ),
    _scenario(
        "empty_intent_inventory_cannot_pass_by_vacuity",
        "A non-trivial revision needs admitted intent or an evidence-bound no-intent rationale.",
        AuthorityCase(
            "empty_intent_inventory_without_rationale",
            intent_present_or_evidence_bound_no_intent=False,
        ),
        _expect_violation(
            "revision_intent_lineage_is_exact_and_resolved",
            "vacuous empty intent acceptance is rejected",
        ),
    ),
    _scenario(
        "accepted_intent_requires_model_effect_or_gap",
        "Every accepted contribution must map to changed models or an explicit gap disposition.",
        AuthorityCase(
            "accepted_intent_unresolved",
            accepted_intent_effects_resolved=False,
        ),
        _expect_violation(
            "revision_intent_lineage_is_exact_and_resolved",
            "unresolved accepted intent is rejected",
        ),
    ),
    _scenario(
        "conflicting_accepted_intent_blocks_activation",
        "Conflicting accepted contributions cannot activate together.",
        AuthorityCase(
            "intent_conflict_ignored",
            intent_conflicts_block_activation=False,
        ),
        _expect_violation(
            "revision_intent_lineage_is_exact_and_resolved",
            "ignored intent conflict is rejected",
        ),
    ),
    _scenario(
        "latest_delta_cannot_stand_for_whole_system_intent",
        "The accepted revision owns one cumulative current-intent view in addition to its revision-local delta.",
        AuthorityCase(
            "latest_delta_used_as_current_intent",
            cumulative_intent_view_inside_current_revision=False,
        ),
        _expect_violation(
            "revision_intent_lineage_is_exact_and_resolved",
            "latest-delta-as-current intent is rejected",
        ),
    ),
    _scenario(
        "every_prior_active_intent_needs_one_transition",
        "A prior active contribution cannot vanish while the current view is folded.",
        AuthorityCase(
            "prior_active_intent_silently_dropped",
            prior_active_intent_transitions_complete=False,
        ),
        _expect_violation(
            "revision_intent_lineage_is_exact_and_resolved",
            "missing cumulative intent transition is rejected",
        ),
    ),
    _scenario(
        "changed_contribution_identity_requires_supersession",
        "Reusing one contribution id with different content cannot create implicit last-write-wins authority.",
        AuthorityCase(
            "same_intent_id_changed_fingerprint",
            intent_identity_changes_use_explicit_supersession=False,
        ),
        _expect_violation(
            "revision_intent_lineage_is_exact_and_resolved",
            "silent contribution replacement is rejected",
        ),
    ),
    _scenario(
        "all_active_intent_sources_are_reverified",
        "Revision construction rechecks every cumulative active source, not only the current delta.",
        AuthorityCase(
            "unchanged_active_intent_source_is_stale",
            active_intent_sources_all_reverified=False,
        ),
        _expect_violation(
            "revision_intent_lineage_is_exact_and_resolved",
            "stale cumulative intent source is rejected",
        ),
    ),
    _scenario(
        "active_direct_intent_source_requires_owner_model_input",
        "A current direct-file intent source must participate in its exact logical owner model identity.",
        AuthorityCase(
            "active_intent_source_missing_from_logical_owner_inputs",
            active_direct_intent_sources_bound_to_logical_owner_inputs=False,
        ),
        _expect_violation(
            "revision_intent_lineage_is_exact_and_resolved",
            "detached intent source owner input is rejected",
        ),
    ),
    _scenario(
        "model_owner_denominator_is_independently_complete",
        "The candidate snapshot independently supplies every and only current model owner required by intent coverage.",
        AuthorityCase(
            "intent_view_shrinks_model_owner_denominator",
            current_model_owner_denominator_exact=False,
        ),
        _expect_violation(
            "revision_intent_lineage_is_exact_and_resolved",
            "shrunk model-owner denominator is rejected",
        ),
    ),
    _scenario(
        "every_model_owner_has_one_exact_effective_binding",
        "Each current owner binds active intent through its exact realization relation without a root fallback.",
        AuthorityCase(
            "model_owner_uses_root_intent_fallback",
            current_model_owner_bindings_exact=False,
        ),
        _expect_violation(
            "revision_intent_lineage_is_exact_and_resolved",
            "missing or fallback model-owner binding is rejected",
        ),
    ),
    _scenario(
        "legacy_intent_revision_is_not_a_current_fallback",
        "After direct migration, normal authority loading accepts only the current cumulative-intent schema.",
        AuthorityCase(
            "legacy_revision_read_as_current_intent",
            legacy_intent_schema_has_no_current_fallback=False,
        ),
        _expect_violation(
            "revision_intent_lineage_is_exact_and_resolved",
            "legacy current-intent fallback is rejected",
        ),
    ),
    _scenario(
        "candidate_isolation_required",
        "Experiment construction cannot mutate the observed head.",
        AuthorityCase("candidate_mutates_observed", candidate_isolated=False),
        _expect_violation(
            "candidates_never_mutate_observed_authority",
            "candidate mutation is rejected",
        ),
    ),
    _scenario(
        "revision_builder_rejects_stale_parent_evidence",
        "A passing parent receipt cannot build a revision after its governed inputs drift.",
        AuthorityCase(
            "revision_builder_stale_parent",
            revision_builder_receipt_exact_current=False,
        ),
        _expect_violation(
            "revision_generation_is_current_and_pointer_free",
            "stale revision-build evidence is rejected",
        ),
    ),
    _scenario(
        "revision_builder_requires_one_exact_leaf_receipt_per_native_owner",
        "Each affected native owner must bind its own exact-current leaf receipt; the parent composition receipt proves only the complete parent run.",
        AuthorityCase(
            "revision_builder_copies_parent_receipt_into_owner_leaves",
            revision_builder_native_owner_leaf_receipts_unique=False,
        ),
        _expect_violation(
            "revision_generation_is_current_and_pointer_free",
            "parent receipt reuse across native owners is rejected",
        ),
    ),
    _scenario(
        "revision_builder_requires_one_explicit_model_binding_per_native_owner_route",
        "A green full parent cannot close an affected native owner whose route has no explicit semantic model binding.",
        AuthorityCase(
            "revision_builder_missing_native_owner_model_binding",
            revision_builder_native_owner_model_map_complete=False,
        ),
        _expect_violation(
            "revision_generation_is_current_and_pointer_free",
            "missing native-owner semantic model binding is rejected",
        ),
    ),
    _scenario(
        "revision_builder_rejects_relabeled_scoped_parent",
        "A scoped run cannot become full evidence by rewriting and rehashing its parent wrapper.",
        AuthorityCase(
            "revision_builder_accepts_relabeled_scoped_parent",
            revision_builder_full_parent_execution_bound=False,
        ),
        _expect_violation(
            "revision_generation_is_current_and_pointer_free",
            "relabeled scoped parent is rejected",
        ),
    ),
    _scenario(
        "revision_builder_rejects_caller_forged_native_owner_verification",
        "A caller cannot make native-owner evidence current by relabeling a receipt or self-reporting a passing verification.",
        AuthorityCase(
            "revision_builder_trusts_caller_native_owner_verification",
            revision_builder_native_owner_independently_verified=False,
        ),
        _expect_violation(
            "revision_generation_is_current_and_pointer_free",
            "caller-forged native-owner verification is rejected",
        ),
    ),
    _scenario(
        "revision_builder_rejects_repeated_complete_child_collection",
        "All affected native owners must derive their distinct subsets from one frozen, independently verified model-child observation.",
        AuthorityCase(
            "revision_builder_rebuilds_complete_child_closure_per_owner",
            revision_builder_one_frozen_child_observation=False,
        ),
        _expect_violation(
            "revision_generation_is_current_and_pointer_free",
            "repeated complete child-closure collection is rejected",
        ),
    ),
    _scenario(
        "revision_builder_requires_final_identity_freshness",
        "A frozen verified bundle cannot support publication until one fresh identity comparison proves its source, environment, parent, children, and aggregates unchanged.",
        AuthorityCase(
            "revision_builder_omits_final_identity_freshness",
            revision_builder_final_identity_freshness_passed=False,
        ),
        _expect_violation(
            "revision_generation_is_current_and_pointer_free",
            "missing final identity freshness is rejected",
        ),
    ),
    _scenario(
        "revision_builder_rejects_canonical_receipt_disappearance",
        "Aggregate and mapped child receipts must remain exact-current in the canonical store through revision publication.",
        AuthorityCase(
            "revision_builder_uses_deleted_canonical_owner_evidence",
            revision_builder_canonical_store_stable_through_publication=False,
        ),
        _expect_violation(
            "revision_generation_is_current_and_pointer_free",
            "canonical receipt disappearance is rejected",
        ),
    ),
    _scenario(
        "revision_builder_cannot_activate_authority",
        "Generation can persist candidates and revisions but cannot move the observed pointer.",
        AuthorityCase(
            "revision_builder_moves_pointer",
            revision_builder_pointer_unchanged=False,
        ),
        _expect_violation(
            "revision_generation_is_current_and_pointer_free",
            "generation-side activation is rejected",
        ),
    ),
    _scenario(
        "unbounded_full_coverage_rejected",
        "Full coverage without a finite universe is invalid.",
        AuthorityCase("unbounded_coverage", finite_coverage_boundary=False),
        _expect_violation(
            "coverage_claim_is_finite_set_equality",
            "unbounded coverage is rejected",
        ),
    ),
    _scenario(
        "declared_optional_local_model_cannot_disappear_from_coverage",
        "A declared non-excluded model remains required when its model or runner is absent.",
        AuthorityCase(
            "optional_local_filtered_out",
            declared_materialized_model_sets_equal=False,
        ),
        _expect_violation(
            "coverage_claim_is_finite_set_equality",
            "declared-to-materialized shrinkage is rejected",
        ),
    ),
    _scenario(
        "partial_multi_model_activation_rejected",
        "A passing member cannot activate independently.",
        AuthorityCase(
            "partial_member_activation",
            no_partial_member_activation=False,
        ),
        _expect_violation(
            "revision_set_closes_as_one_unit",
            "partial activation is rejected",
        ),
    ),
    _scenario(
        "affected_sibling_must_close",
        "A relation change must include affected siblings and evidence.",
        AuthorityCase(
            "missing_affected_sibling",
            affected_closure_complete=False,
        ),
        _expect_violation(
            "revision_set_closes_as_one_unit",
            "incomplete affected closure is rejected",
        ),
    ),
    _scenario(
        "caller_declared_diff_cannot_replace_canonical_diff",
        "A caller cannot omit a changed owner, coverage row, gap, or sibling.",
        AuthorityCase(
            "caller_shrinks_diff",
            diff_independently_derived=False,
        ),
        _expect_violation(
            "revision_set_closes_as_one_unit",
            "caller-narrowed diff is rejected",
        ),
    ),
    _scenario(
        "two_receipts_cannot_cover_only_two_of_thirty_three_ids",
        "Receipt-list equality cannot hide uncovered affected identities.",
        AuthorityCase(
            "receipt_list_hides_uncovered_ids",
            evidence_coverage_union_exact=False,
        ),
        _expect_violation(
            "revision_set_closes_as_one_unit",
            "incomplete evidence coverage union is rejected",
        ),
    ),
    _scenario(
        "stale_base_blocks_activation",
        "A candidate based on an older observed head cannot activate.",
        AuthorityCase("stale_base", expected_head_matches=False),
        _expect_violation(
            "activation_is_compare_and_swap_pointer_last",
            "stale-base activation is rejected",
        ),
    ),
    _scenario(
        "pointer_first_crash_is_rejected",
        "The current pointer cannot move before immutable evidence exists.",
        AuthorityCase(
            "pointer_before_receipts",
            immutable_records_before_pointer=False,
        ),
        _expect_violation(
            "activation_is_compare_and_swap_pointer_last",
            "pointer-first activation is rejected",
        ),
    ),
    _scenario(
        "same_head_live_source_drift_blocks_activation",
        "An unchanged pointer cannot authorize a candidate after live input drift.",
        AuthorityCase(
            "same_head_live_drift",
            lock_held_live_candidate_exact=False,
        ),
        _expect_violation(
            "activation_is_compare_and_swap_pointer_last",
            "lock-held live candidate drift is rejected",
        ),
    ),
    _scenario(
        "pre_pointer_live_resample_must_stay_exact",
        "A final governed-source resample must match before pointer replacement.",
        AuthorityCase(
            "pre_pointer_resample_drift",
            final_live_resample_exact=False,
        ),
        _expect_violation(
            "activation_is_compare_and_swap_pointer_last",
            "final live resample drift is rejected",
        ),
    ),
    _scenario(
        "observed_snapshot_must_match_implementation",
        "A target snapshot cannot masquerade as observed after code remains old.",
        AuthorityCase(
            "observed_subject_mismatch",
            observed_subject_matches_software=False,
        ),
        _expect_violation(
            "observed_head_matches_real_software",
            "observed subject mismatch is rejected",
        ),
    ),
    _scenario(
        "global_subject_cannot_fan_out_into_every_instance",
        "A global source revision cannot invalidate unrelated local model identities.",
        AuthorityCase(
            "global_subject_fanout",
            instance_identity_is_local=False,
        ),
        _expect_violation(
            "local_identity_and_global_provenance_are_separate",
            "global-to-local identity fan-out is rejected",
        ),
    ),
    _scenario(
        "unknown_impact_cannot_fall_back_to_run_all",
        "An unmapped source path blocks before model producers start.",
        AuthorityCase(
            "unknown_impact_runs_all",
            unknown_impact_blocks=False,
        ),
        _expect_violation(
            "impact_and_public_closure_fail_closed",
            "unknown-impact run-all fallback is rejected",
        ),
    ),
    _scenario(
        "release_requires_public_authority_closure",
        "The source release must contain the current authority records.",
        AuthorityCase(
            "authority_records_ignored",
            public_authority_closure_complete=False,
        ),
        _expect_violation(
            "impact_and_public_closure_fail_closed",
            "ignored model authority closure is rejected",
        ),
    ),
    _scenario(
        "legacy_authority_schema_cannot_remain_a_second_reader",
        "An incompatible persisted authority schema must migrate directly to the sole current schema.",
        AuthorityCase(
            "legacy_authority_dual_reader",
            incompatible_schema_has_one_direct_current_migration=False,
        ),
        _expect_violation(
            "incompatible_authority_schema_has_no_dual_reader",
            "legacy authority dual-read success is rejected",
        ),
    ),
    _scenario(
        "maturation_cannot_use_caller_narrowed_coverage",
        "A caller cannot shrink the independent task coverage universe to manufacture closure.",
        AuthorityCase(
            "maturation_caller_shrinks_coverage",
            maturation_task_and_coverage_are_frozen=False,
        ),
        _expect_violation(
            "maturation_proves_behavior_instead_of_accepting_self_report",
            "caller-narrowed maturation coverage is rejected",
        ),
    ),
    _scenario(
        "maturation_cannot_accept_resolved_boolean_as_evidence",
        "A caller-authored resolved flag cannot replace an exact current native receipt.",
        AuthorityCase(
            "maturation_self_reported_resolution",
            maturation_receipts_bind_exact_candidate=False,
        ),
        _expect_violation(
            "maturation_proves_behavior_instead_of_accepting_self_report",
            "self-reported maturation resolution is rejected",
        ),
    ),
    _scenario(
        "addressable_maturation_gap_cannot_stop_the_loop",
        "An addressable gap must produce another candidate iteration rather than a terminal claim.",
        AuthorityCase(
            "maturation_upgrade_marked_terminal",
            addressable_maturation_gap_keeps_iteration_open=False,
        ),
        _expect_violation(
            "maturation_proves_behavior_instead_of_accepting_self_report",
            "premature maturation termination is rejected",
        ),
    ),
    _scenario(
        "inventory_only_cannot_claim_whole_system_understanding",
        "Listing every model without semantic dispositions and consumer relations is not whole-system understanding.",
        AuthorityCase(
            "inventory_only_semantics",
            semantic_model_dispositions_complete=False,
            semantic_model_relations_complete=False,
        ),
        _expect_violation(
            "whole_system_understanding_is_semantic_and_current",
            "inventory-only understanding is rejected",
        ),
    ),
    _scenario(
        "five_model_slice_cannot_claim_whole_system_understanding",
        "A green five-model slice cannot stand in for the exact current model universe.",
        AuthorityCase(
            "five_model_slice",
            semantic_model_universe_exact=False,
        ),
        _expect_violation(
            "whole_system_understanding_is_semantic_and_current",
            "partial semantic slice is rejected",
        ),
    ),
    _scenario(
        "empty_semantic_derivation_fingerprint_is_rejected",
        "A semantic table without its content-addressed derivation base is not current evidence.",
        AuthorityCase(
            "empty_semantic_derivation_fingerprint",
            semantic_derivation_fingerprint_present=False,
        ),
        _expect_violation(
            "whole_system_understanding_is_semantic_and_current",
            "empty semantic derivation fingerprint is rejected",
        ),
    ),
    _scenario(
        "unverified_semantic_artifact_cannot_claim_completion",
        "A defined semantic mesh remains a candidate until terminal native evidence is independently verified.",
        AuthorityCase(
            "unverified_semantic_artifact",
            semantic_completion_evidence_terminal_verified=False,
        ),
        _expect_violation(
            "whole_system_understanding_is_semantic_and_current",
            "unverified semantic completion artifact is rejected",
        ),
    ),
    _scenario(
        "unfrozen_provider_registry_cannot_support_broad_blueprint",
        "A broad target blueprint requires one exact current provider denominator.",
        AuthorityCase(
            "unfrozen_provider_registry",
            target_provider_registry_exact_current=False,
        ),
        _expect_violation(
            "whole_system_understanding_is_semantic_and_current",
            "unfrozen provider registry is rejected",
        ),
    ),
    _scenario(
        "stale_target_snapshot_cannot_support_broad_blueprint",
        "Target descriptor and provider results must share one current revision-bound snapshot.",
        AuthorityCase(
            "stale_target_snapshot",
            target_snapshot_exact_current=False,
        ),
        _expect_violation(
            "whole_system_understanding_is_semantic_and_current",
            "stale target-system snapshot is rejected",
        ),
    ),
    _scenario(
        "provider_lineage_cannot_be_omitted_from_broad_blueprint",
        "A broad static claim consumes its exact provider registry and snapshot lineage.",
        AuthorityCase(
            "provider_lineage_omitted",
            broad_blueprint_claim_consumes_provider_lineage=False,
        ),
        _expect_violation(
            "whole_system_understanding_is_semantic_and_current",
            "provider-lineage-free broad claim is rejected",
        ),
    ),
    _scenario(
        "internally_consistent_provider_payload_cannot_replace_current_native_report",
        "A freshly refrozen provider bundle must still match every current native project report.",
        AuthorityCase(
            "counterfeit_provider_payload",
            target_provider_payload_matches_current_native_reports=False,
        ),
        _expect_violation(
            "whole_system_understanding_is_semantic_and_current",
            "provider payload divergence is rejected",
        ),
    ),
    _scenario(
        "semantic_mesh_fingerprint_must_be_derived_from_reviewed_topology",
        "A caller-selected mesh fingerprint cannot identify unchanged reviewed topology.",
        AuthorityCase(
            "counterfeit_semantic_mesh_fingerprint",
            semantic_mesh_identity_derived_from_topology=False,
        ),
        _expect_violation(
            "whole_system_understanding_is_semantic_and_current",
            "caller-selected semantic mesh identity is rejected",
        ),
    ),
    _scenario(
        "topology_cannot_consume_ghost_runtime_evidence",
        "Matching evidence labels in child, relation, and reattachment remain invalid without a current owner-bound artifact.",
        AuthorityCase(
            "ghost_topology_runtime_evidence",
            topology_runtime_evidence_exact_current=False,
        ),
        _expect_violation(
            "whole_system_understanding_is_semantic_and_current",
            "ghost topology evidence is rejected",
        ),
    ),
    _scenario(
        "affected_reader_must_follow_every_semantic_dependency",
        "A changed producer, delegate, or support owner must invalidate its exact semantic dependants.",
        AuthorityCase(
            "affected_reader_omits_non_parent_dependency",
            affected_semantic_relation_closure_complete=False,
        ),
        _expect_violation(
            "whole_system_understanding_is_semantic_and_current",
            "incomplete semantic affected closure is rejected",
        ),
    ),
    _scenario(
        "raw_manifest_cannot_self_certify_semantic_mesh",
        "A caller cannot repeat one arbitrary mesh fingerprint across manifest and command input to obtain blueprint authority.",
        AuthorityCase(
            "raw_manifest_self_certifies_mesh",
            raw_manifest_route_has_no_blueprint_authority=False,
        ),
        _expect_violation(
            "whole_system_understanding_is_semantic_and_current",
            "alternate raw-manifest authority is rejected",
        ),
    ),
    _scenario(
        "topology_requires_one_root_sentinel",
        "A topology with zero root-sentinel nodes is rejected by the same topology-authority invariant as a duplicate root.",
        AuthorityCase(
            "topology_missing_root_sentinel",
            topology_root_sentinel_present=False,
        ),
        _expect_violation(
            "topology_authority_is_typed_current_and_independently_evidenced",
            "a missing root sentinel is rejected",
        ),
    ),
    _scenario(
        "topology_rejects_two_root_sentinels",
        "A topology with two root-sentinel nodes is rejected by the same topology-authority invariant as a missing root.",
        AuthorityCase(
            "topology_duplicates_root_sentinel",
            topology_root_sentinel_unique=False,
        ),
        _expect_violation(
            "topology_authority_is_typed_current_and_independently_evidenced",
            "a duplicate root sentinel is rejected",
        ),
    ),
    _scenario(
        "topology_rejects_second_structural_parent",
        "A child model has exactly one structural parent in the authoritative topology.",
        AuthorityCase(
            "topology_has_second_structural_parent",
            topology_structural_parent_unique=False,
        ),
        _expect_violation(
            "topology_authority_is_typed_current_and_independently_evidenced",
            "a second structural parent is rejected",
        ),
    ),
    _scenario(
        "topology_keeps_cross_boundary_support_non_structural",
        "A support relationship may cross boundaries without becoming a second structural parent.",
        AuthorityCase(
            "topology_promotes_cross_boundary_support_to_parent",
            topology_cross_boundary_support_non_structural=False,
        ),
        _expect_violation(
            "topology_authority_is_typed_current_and_independently_evidenced",
            "cross-boundary support promoted to parent is rejected",
        ),
    ),
    _scenario(
        "topology_parent_receipt_proves_only_composition",
        "The full parent receipt proves only the exact declared-child composition and cannot fill any child evidence slot.",
        AuthorityCase(
            "topology_copies_parent_receipt_into_child_slots",
            topology_parent_receipt_composition_only=False,
        ),
        _expect_violation(
            "topology_authority_is_typed_current_and_independently_evidenced",
            "parent receipt promotion to child evidence is rejected",
        ),
    ),
    _scenario(
        "topology_requires_exact_child_receipt_coverage",
        "Every declared child model has one current receipt and no foreign child receipt is added.",
        AuthorityCase(
            "topology_omits_one_declared_child_receipt",
            topology_child_receipt_coverage_exact=False,
        ),
        _expect_violation(
            "topology_authority_is_typed_current_and_independently_evidenced",
            "incomplete child receipt coverage is rejected",
        ),
    ),
    _scenario(
        "topology_rejects_stale_child_receipt",
        "Every child receipt must be exact-current for the governed snapshot and execution.",
        AuthorityCase(
            "topology_uses_stale_child_receipt",
            topology_child_receipts_exact_current=False,
        ),
        _expect_violation(
            "topology_authority_is_typed_current_and_independently_evidenced",
            "stale child receipt is rejected",
        ),
    ),
    _scenario(
        "topology_rejects_foreign_owner_child_receipt",
        "Each child receipt binds the exact child model and its execution owner.",
        AuthorityCase(
            "topology_uses_foreign_owner_child_receipt",
            topology_child_receipts_owner_bound=False,
        ),
        _expect_violation(
            "topology_authority_is_typed_current_and_independently_evidenced",
            "foreign-owner child receipt is rejected",
        ),
    ),
    _scenario(
        "topology_rejects_duplicate_child_receipt_identity",
        "Distinct child models cannot share one projected receipt identity.",
        AuthorityCase(
            "topology_duplicates_child_receipt_identity",
            topology_child_receipts_distinct=False,
        ),
        _expect_violation(
            "topology_authority_is_typed_current_and_independently_evidenced",
            "duplicate child receipt identity is rejected",
        ),
    ),
    _scenario(
        "topology_feedback_relation_classification_must_be_complete",
        "Feedback, retry, and repair relation kinds must all be classified into the bounded feedback graph.",
        AuthorityCase(
            "topology_feedback_relation_classification_incomplete",
            topology_feedback_relation_classification_complete=False,
        ),
        _expect_violation(
            "topology_authority_is_typed_current_and_independently_evidenced",
            "incomplete feedback relation classification is rejected",
        ),
    ),
    _scenario(
        "topology_feedback_loop_requires_progress_contract",
        "Every explicit feedback SCC has an explicit finite-progress contract.",
        AuthorityCase(
            "topology_feedback_loop_has_no_progress_contract",
            topology_feedback_progress_contract_present=False,
        ),
        _expect_violation(
            "topology_authority_is_typed_current_and_independently_evidenced",
            "missing feedback progress contract is rejected",
        ),
    ),
    _scenario(
        "topology_retry_loop_requires_progress_contract",
        "Every retry SCC has an explicit finite-progress contract.",
        AuthorityCase(
            "topology_retry_loop_has_no_progress_contract",
            topology_retry_progress_contract_present=False,
        ),
        _expect_violation(
            "topology_authority_is_typed_current_and_independently_evidenced",
            "missing retry progress contract is rejected",
        ),
    ),
    _scenario(
        "topology_repair_loop_requires_progress_contract",
        "Every repair SCC has an explicit finite-progress contract.",
        AuthorityCase(
            "topology_repair_loop_has_no_progress_contract",
            topology_repair_progress_contract_present=False,
        ),
        _expect_violation(
            "topology_authority_is_typed_current_and_independently_evidenced",
            "missing repair progress contract is rejected",
        ),
    ),
    _scenario(
        "topology_feedback_loop_requires_current_progress_evidence",
        "A feedback, retry, or repair contract remains unproved when its progress evidence is missing or stale.",
        AuthorityCase(
            "topology_feedback_loop_uses_stale_progress_evidence",
            topology_feedback_progress_evidence_exact_current=False,
        ),
        _expect_violation(
            "topology_authority_is_typed_current_and_independently_evidenced",
            "stale feedback progress evidence is rejected",
        ),
    ),
    _scenario(
        "topology_feedback_loop_rejects_stale_progress_contract",
        "A progress contract from another semantic-topology revision cannot license a current feedback, retry, or repair SCC.",
        AuthorityCase(
            "topology_feedback_loop_uses_stale_progress_contract",
            topology_feedback_progress_contract_exact_current=False,
        ),
        _expect_violation(
            "topology_authority_is_typed_current_and_independently_evidenced",
            "stale feedback progress contract is rejected",
        ),
    ),
    _scenario(
        "checked_in_semantic_declaration_cannot_self_certify_topology_currentness",
        "The semantic declaration describes child and feedback relationships but needs independently produced current evidence.",
        AuthorityCase(
            "checked_in_declaration_self_certifies_topology_currentness",
            topology_currentness_independent_of_checked_in_declaration=False,
        ),
        _expect_violation(
            "topology_authority_is_typed_current_and_independently_evidenced",
            "self-certified topology currentness is rejected",
        ),
    ),
    _scenario(
        "project_document_must_carry_its_intent_authority",
        "A portable project document carries the exact intent inventory consumed by behavior and readiness review.",
        AuthorityCase(
            "intent_supplied_only_outside_project_document",
            project_document_carries_intent_inventory=False,
        ),
        _expect_violation(
            "whole_system_understanding_is_semantic_and_current",
            "intent authority cannot live in an optional side argument",
        ),
    ),
    _scenario(
        "portable_export_preserves_every_blueprint_layer",
        "A canonical export carries provider evidence, behavior, topology, code and test bindings, resources, intent, indexes, and readiness.",
        AuthorityCase(
            "portable_export_omits_one_layer",
            canonical_export_preserves_all_blueprint_layers=False,
        ),
        _expect_violation(
            "whole_system_understanding_is_semantic_and_current",
            "partial projection cannot claim portable blueprint identity",
        ),
    ),
    _scenario(
        "export_completion_does_not_promote_model_depth",
        "A deterministic export can preserve a growing model while its readiness gaps remain visible.",
        AuthorityCase(
            "export_success_promotes_model_readiness",
            export_status_is_distinct_from_model_readiness=False,
        ),
        _expect_violation(
            "whole_system_understanding_is_semantic_and_current",
            "materialization status cannot replace readiness status",
        ),
    ),
    _scenario(
        "pointer_only_operational_rollback_rejected",
        "Model authority cannot roll back while implementation effects remain new.",
        AuthorityCase(
            "pointer_only_rollback",
            implementation_effects_restored=False,
        ),
        _expect_violation(
            "rollback_restores_reality_before_authority",
            "pointer-only rollback is rejected",
        ),
    ),
    _scenario(
        "irreversible_effect_needs_forward_repair",
        "Irreversible effects cannot be called an exact rollback.",
        AuthorityCase(
            "irreversible_exact_rollback_claim",
            irreversible_effect_not_exact_rollback=False,
        ),
        _expect_violation(
            "rollback_restores_reality_before_authority",
            "false exact rollback is rejected",
        ),
    ),
    _scenario(
        "rollback_receipt_cannot_masquerade_as_revision",
        "A successful rollback uses an accepted reverse revision as current authority.",
        AuthorityCase(
            "rollback_receipt_as_revision",
            rollback_is_reverse_revision=False,
        ),
        _expect_violation(
            "rollback_restores_reality_before_authority",
            "untyped rollback transition identity is rejected",
        ),
    ),
    _scenario(
        "old_rollback_contract_cannot_replay_at_same_snapshot",
        "A later generation with the same snapshot still has a different full head.",
        AuthorityCase(
            "rollback_snapshot_only_replay",
            rollback_origin_head_matches=False,
        ),
        _expect_violation(
            "rollback_restores_reality_before_authority",
            "snapshot-only rollback replay is rejected",
        ),
    ),
)


def run_review():
    return review_scenarios(SCENARIOS)


if __name__ == "__main__":
    report = run_review()
    print(report.format_text())
    raise SystemExit(0 if report.ok else 1)
