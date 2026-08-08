"""FlowGuard rollout model for architecture reduction governance.

Risk Purpose Header:
Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: review the model-to-code architecture reduction route before
implementation. It guards both behavior-preserving contraction and deliberate
retirement of behavior that the current product goal no longer needs. It
rejects retirement without a complete current responsibility inventory,
replacement owners, migrated negative cases, and zero compatibility survival.
It also classifies retained-route internal steps, while measured operation or
payload cost can prioritize review but can never replace equivalence or unique
safety/evidence-owner proof.

Run:
python .flowguard/architecture_reduction/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from flowguard import FunctionResult, Invariant, InvariantResult, Scenario, ScenarioExpectation, Workflow
from flowguard.review import review_scenarios


@dataclass(frozen=True)
class ArchitectureReductionCase:
    name: str
    existing_model_grounded: bool = True
    observable_contract_declared: bool = True
    code_mapping_present: bool = True
    candidates_classified: bool = True
    proof_status_visible: bool = True
    risky_candidates_kept_visible: bool = True
    public_entrypoint_structuremesh_gate: bool = True
    target_structure_handoff: bool = True
    completed_candidates_not_requeued: bool = True
    companion_route_triggers: bool = True
    no_direct_code_rewrite: bool = True
    validation_gates_visible: bool = True
    reduction_mode: str = "contract"
    retirement_proof_present: bool = False
    retirement_proof_current: bool = True
    retirement_responsibilities_complete: bool = True
    retirement_replacement_owners_current: bool = True
    retirement_negative_cases_preserved: bool = True
    retirement_has_no_compatibility_survival: bool = True
    ordinary_contraction_behavior_equivalent: bool = True
    expected_candidate_inventory_declared: bool = True
    expected_candidates_materialized: bool = True
    all_reduction_signal_families_dispositioned: bool = True
    self_blueprint_identity_exact_current: bool = True
    retain_and_unresolved_dispositions_independently_evidenced: bool = True
    candidate_signal_dispositions_are_relation_aware: bool = True
    candidate_retain_authority_is_independent: bool = True
    same_commitment_candidates_stay_unresolved: bool = True
    retained_implementation_necessity_witness_current_and_independent: bool = True
    test_and_model_validation_evidence_namespaces_separate: bool = True
    identifier_only_semantic_difference_rejected: bool = True
    public_role_without_promise_rejected: bool = True
    external_promise_exact_model_code_test_binding: bool = True
    maintenance_lexical_name_is_signal_only: bool = True
    maintenance_candidate_requires_exact_related_multi_surface: bool = True
    reduction_proofs_independently_verified: bool = True
    reduction_proofs_use_executed_child_receipts: bool = True
    candidate_tests_are_semantically_executed: bool = True
    parity_replays_bound_behavior_oracles: bool = True
    reduction_proof_store_is_canonical: bool = True
    reduction_proof_store_is_confined_non_reparse: bool = True
    reduction_proof_execution_unique_per_candidate: bool = True
    facade_evidence_derived_from_current_authorities: bool = True
    caller_edges_canonical_and_unambiguous: bool = True
    conflicting_member_actions_have_unique_primary: bool = True
    reduction_review_final_currentness_rechecked: bool = True
    final_blueprint_denominator_rebuilt: bool = True
    review_and_proof_execution_are_separate: bool = True
    audit_auto_discovery_one_exact_current_canonical_aggregate: bool = True
    audit_proof_batch_reuse_explicit_finite: bool = True
    audit_injected_registry_rejected: bool = True
    audit_stale_history_ignored: bool = True
    audit_duplicate_current_aggregate_blocked: bool = True
    canonical_relation_provenance_materialized: bool = True
    facade_delegation_current: bool = True
    facade_has_no_independent_success: bool = True
    caller_relations_indexed_once: bool = True
    self_maintenance_blueprint_built_once: bool = True
    compact_projection_avoids_full_expansion: bool = True
    large_immutable_report_fingerprints_cached: bool = True
    large_payload_fingerprints_streamed: bool = True
    candidate_evidence_neighborhoods_content_addressed_once: bool = True
    comparison_candidate_batches_finite_and_bounded: bool = True
    candidate_evidence_references_exact_and_fail_closed: bool = True
    affected_object_reference_denominator_indexed_once: bool = True
    retained_route_internal_steps_classified: bool = True
    step_action_vocabulary_current: bool = True
    step_cost_evidence_current: bool = True
    step_cost_is_priority_only: bool = True
    unique_safety_responsibilities_preserved: bool = True
    on_demand_triggers_explicit: bool = True
    audit_complete: bool = True
    step_decision_complete: bool = True
    action_authorized_candidate_ids: tuple[str, ...] = ()
    unresolved_candidate_ids: tuple[str, ...] = ()
    unresolved_step_ids: tuple[str, ...] = ()
    cleanup_release_ready: bool = True
    review_status: str = "pass"


@dataclass(frozen=True)
class ArchitectureReductionPolicy:
    case_name: str = ""
    existing_model_grounded: bool = False
    observable_contract_declared: bool = False
    code_mapping_present: bool = False
    candidates_classified: bool = False
    proof_status_visible: bool = False
    risky_candidates_kept_visible: bool = False
    public_entrypoint_structuremesh_gate: bool = False
    target_structure_handoff: bool = False
    completed_candidates_not_requeued: bool = False
    companion_route_triggers: bool = False
    no_direct_code_rewrite: bool = False
    validation_gates_visible: bool = False
    reduction_mode: str = "contract"
    retirement_proof_present: bool = False
    retirement_proof_current: bool = False
    retirement_responsibilities_complete: bool = False
    retirement_replacement_owners_current: bool = False
    retirement_negative_cases_preserved: bool = False
    retirement_has_no_compatibility_survival: bool = False
    ordinary_contraction_behavior_equivalent: bool = False
    expected_candidate_inventory_declared: bool = False
    expected_candidates_materialized: bool = False
    all_reduction_signal_families_dispositioned: bool = False
    self_blueprint_identity_exact_current: bool = False
    retain_and_unresolved_dispositions_independently_evidenced: bool = False
    candidate_signal_dispositions_are_relation_aware: bool = False
    candidate_retain_authority_is_independent: bool = False
    same_commitment_candidates_stay_unresolved: bool = False
    retained_implementation_necessity_witness_current_and_independent: bool = False
    test_and_model_validation_evidence_namespaces_separate: bool = False
    identifier_only_semantic_difference_rejected: bool = False
    public_role_without_promise_rejected: bool = False
    external_promise_exact_model_code_test_binding: bool = False
    maintenance_lexical_name_is_signal_only: bool = False
    maintenance_candidate_requires_exact_related_multi_surface: bool = False
    reduction_proofs_independently_verified: bool = False
    reduction_proofs_use_executed_child_receipts: bool = False
    candidate_tests_are_semantically_executed: bool = False
    parity_replays_bound_behavior_oracles: bool = False
    reduction_proof_store_is_canonical: bool = False
    reduction_proof_store_is_confined_non_reparse: bool = False
    reduction_proof_execution_unique_per_candidate: bool = False
    facade_evidence_derived_from_current_authorities: bool = False
    caller_edges_canonical_and_unambiguous: bool = False
    conflicting_member_actions_have_unique_primary: bool = False
    reduction_review_final_currentness_rechecked: bool = False
    final_blueprint_denominator_rebuilt: bool = False
    review_and_proof_execution_are_separate: bool = False
    audit_auto_discovery_one_exact_current_canonical_aggregate: bool = False
    audit_proof_batch_reuse_explicit_finite: bool = False
    audit_injected_registry_rejected: bool = False
    audit_stale_history_ignored: bool = False
    audit_duplicate_current_aggregate_blocked: bool = False
    canonical_relation_provenance_materialized: bool = False
    facade_delegation_current: bool = False
    facade_has_no_independent_success: bool = False
    caller_relations_indexed_once: bool = False
    self_maintenance_blueprint_built_once: bool = False
    compact_projection_avoids_full_expansion: bool = False
    large_immutable_report_fingerprints_cached: bool = False
    large_payload_fingerprints_streamed: bool = False
    candidate_evidence_neighborhoods_content_addressed_once: bool = False
    comparison_candidate_batches_finite_and_bounded: bool = False
    candidate_evidence_references_exact_and_fail_closed: bool = False
    affected_object_reference_denominator_indexed_once: bool = False
    retained_route_internal_steps_classified: bool = False
    step_action_vocabulary_current: bool = False
    step_cost_evidence_current: bool = False
    step_cost_is_priority_only: bool = False
    unique_safety_responsibilities_preserved: bool = False
    on_demand_triggers_explicit: bool = False
    audit_complete: bool = False
    step_decision_complete: bool = False
    action_authorized_candidate_ids: tuple[str, ...] = ()
    unresolved_candidate_ids: tuple[str, ...] = ()
    unresolved_step_ids: tuple[str, ...] = ()
    cleanup_release_ready: bool = False
    review_status: str = "not_run"


GOOD_PLAN = ArchitectureReductionCase("good_architecture_reduction_plan")
GOOD_RETIREMENT_PLAN = ArchitectureReductionCase(
    "good_intentional_retirement_plan",
    reduction_mode="retire_behavior",
    retirement_proof_present=True,
)
PROOFLESS_RISKY_KEEP_PLAN = ArchitectureReductionCase(
    "proofless_risky_keep_audit_plan",
    unresolved_candidate_ids=("candidate:proofless",),
    step_decision_complete=False,
    unresolved_step_ids=("candidate-step:proofless",),
    cleanup_release_ready=False,
)
SAFE_UNAPPLIED_PLAN = ArchitectureReductionCase(
    "safe_unapplied_action_plan",
    action_authorized_candidate_ids=("candidate:safe-unapplied",),
    cleanup_release_ready=False,
    review_status="blocked",
)
INCOMPLETE_AUDIT_PLAN = ArchitectureReductionCase(
    "incomplete_audit_plan",
    audit_complete=False,
    cleanup_release_ready=False,
    review_status="blocked",
)
BROKEN_NO_MODEL_GROUNDING = ArchitectureReductionCase("broken_no_model_grounding", existing_model_grounded=False)
BROKEN_NO_OBSERVABLE_CONTRACT = ArchitectureReductionCase(
    "broken_no_observable_contract",
    observable_contract_declared=False,
)
BROKEN_NO_CODE_MAPPING = ArchitectureReductionCase("broken_no_code_mapping", code_mapping_present=False)
BROKEN_UNCLASSIFIED_CANDIDATES = ArchitectureReductionCase("broken_unclassified_candidates", candidates_classified=False)
BROKEN_HIDDEN_PROOF_STATUS = ArchitectureReductionCase("broken_hidden_proof_status", proof_status_visible=False)
BROKEN_RISKY_CANDIDATES_HIDDEN = ArchitectureReductionCase(
    "broken_risky_candidates_hidden",
    risky_candidates_kept_visible=False,
)
BROKEN_PUBLIC_ENTRYPOINT_BYPASS = ArchitectureReductionCase(
    "broken_public_entrypoint_bypass",
    public_entrypoint_structuremesh_gate=False,
)
BROKEN_NO_TARGET_HANDOFF = ArchitectureReductionCase("broken_no_target_handoff", target_structure_handoff=False)
BROKEN_COMPLETED_CANDIDATE_REQUEUED = ArchitectureReductionCase(
    "broken_completed_candidate_requeued",
    completed_candidates_not_requeued=False,
)
BROKEN_NO_COMPANION_TRIGGERS = ArchitectureReductionCase(
    "broken_no_companion_triggers",
    companion_route_triggers=False,
)
BROKEN_DIRECT_REWRITE = ArchitectureReductionCase("broken_direct_rewrite", no_direct_code_rewrite=False)
BROKEN_NO_VALIDATION_GATES = ArchitectureReductionCase("broken_no_validation_gates", validation_gates_visible=False)
BROKEN_CONTRACT_CHANGES_BEHAVIOR = ArchitectureReductionCase(
    "broken_contract_changes_behavior",
    ordinary_contraction_behavior_equivalent=False,
)
BROKEN_RETIREMENT_PROOF_ON_CONTRACT = ArchitectureReductionCase(
    "broken_retirement_proof_on_contract",
    retirement_proof_present=True,
)
BROKEN_RETIREMENT_PROOF_MISSING = ArchitectureReductionCase(
    "broken_retirement_proof_missing",
    reduction_mode="retire_behavior",
    retirement_proof_present=False,
)
BROKEN_RETIREMENT_PROOF_STALE = ArchitectureReductionCase(
    "broken_retirement_proof_stale",
    reduction_mode="retire_behavior",
    retirement_proof_present=True,
    retirement_proof_current=False,
)
BROKEN_RETIREMENT_RESPONSIBILITY_GAP = ArchitectureReductionCase(
    "broken_retirement_responsibility_gap",
    reduction_mode="retire_behavior",
    retirement_proof_present=True,
    retirement_responsibilities_complete=False,
)
BROKEN_RETIREMENT_OWNER_AMBIGUOUS = ArchitectureReductionCase(
    "broken_retirement_owner_ambiguous",
    reduction_mode="retire_behavior",
    retirement_proof_present=True,
    retirement_replacement_owners_current=False,
)
BROKEN_RETIREMENT_NEGATIVE_CASE_ORPHANED = ArchitectureReductionCase(
    "broken_retirement_negative_case_orphaned",
    reduction_mode="retire_behavior",
    retirement_proof_present=True,
    retirement_negative_cases_preserved=False,
)
BROKEN_RETIREMENT_COMPATIBILITY_SURVIVES = ArchitectureReductionCase(
    "broken_retirement_compatibility_survives",
    reduction_mode="retire_behavior",
    retirement_proof_present=True,
    retirement_has_no_compatibility_survival=False,
)
BROKEN_NO_EXPECTED_CANDIDATE_INVENTORY = ArchitectureReductionCase(
    "broken_no_expected_candidate_inventory",
    expected_candidate_inventory_declared=False,
)
BROKEN_OMITTED_EXPECTED_CANDIDATE = ArchitectureReductionCase(
    "broken_omitted_expected_candidate",
    expected_candidates_materialized=False,
)
BROKEN_INCOMPLETE_SIGNAL_FAMILIES = ArchitectureReductionCase(
    "broken_incomplete_signal_families",
    all_reduction_signal_families_dispositioned=False,
)
BROKEN_LABEL_ONLY_SELF_BLUEPRINT = ArchitectureReductionCase(
    "broken_label_only_self_blueprint",
    self_blueprint_identity_exact_current=False,
)
BROKEN_AUTOMATIC_RETAIN_DISPOSITION = ArchitectureReductionCase(
    "broken_automatic_retain_disposition",
    retain_and_unresolved_dispositions_independently_evidenced=False,
)
BROKEN_CANDIDATE_SIGNAL_AUTO_RETAIN = ArchitectureReductionCase(
    "broken_candidate_signal_auto_retain",
    candidate_signal_dispositions_are_relation_aware=False,
)
BROKEN_CANDIDATE_BINDING_SELF_PROVES_RETAIN = ArchitectureReductionCase(
    "broken_candidate_binding_self_proves_retain",
    candidate_retain_authority_is_independent=False,
)
BROKEN_SAME_COMMITMENT_AUTO_RETAIN = ArchitectureReductionCase(
    "broken_same_commitment_auto_retain",
    same_commitment_candidates_stay_unresolved=False,
)
BROKEN_RETAIN_WITHOUT_CURRENT_NECESSITY_WITNESS = ArchitectureReductionCase(
    "broken_retain_without_current_necessity_witness",
    retained_implementation_necessity_witness_current_and_independent=False,
)
BROKEN_MIXED_TEST_AND_MODEL_VALIDATION_EVIDENCE = ArchitectureReductionCase(
    "broken_mixed_test_and_model_validation_evidence",
    test_and_model_validation_evidence_namespaces_separate=False,
)
BROKEN_IDENTIFIER_ONLY_SEMANTIC_DIFFERENCE = ArchitectureReductionCase(
    "broken_identifier_only_semantic_difference",
    identifier_only_semantic_difference_rejected=False,
)
BROKEN_PUBLIC_ROLE_AS_CURRENT_PROMISE = ArchitectureReductionCase(
    "broken_public_role_as_current_promise",
    public_role_without_promise_rejected=False,
)
BROKEN_EXTERNAL_PROMISE_WITHOUT_EXACT_OWNER_BINDING = ArchitectureReductionCase(
    "broken_external_promise_without_exact_owner_binding",
    external_promise_exact_model_code_test_binding=False,
)
BROKEN_ISOLATED_MAINTENANCE_NAME_CANDIDATE = ArchitectureReductionCase(
    "broken_isolated_maintenance_name_candidate",
    maintenance_lexical_name_is_signal_only=False,
)
BROKEN_INEXACT_MAINTENANCE_RELATION_CANDIDATE = ArchitectureReductionCase(
    "broken_inexact_maintenance_relation_candidate",
    maintenance_candidate_requires_exact_related_multi_surface=False,
)
BROKEN_CALLER_FORGED_REDUCTION_PROOF = ArchitectureReductionCase(
    "broken_caller_forged_reduction_proof",
    reduction_proofs_independently_verified=False,
)
BROKEN_SELF_CERTIFIED_LEAF_PROOF = ArchitectureReductionCase(
    "broken_self_certified_leaf_proof",
    reduction_proofs_use_executed_child_receipts=False,
)
BROKEN_EXIT_ZERO_CANDIDATE_TEST = ArchitectureReductionCase(
    "broken_exit_zero_candidate_test",
    candidate_tests_are_semantically_executed=False,
)
BROKEN_METADATA_ONLY_PARITY = ArchitectureReductionCase(
    "broken_metadata_only_parity",
    parity_replays_bound_behavior_oracles=False,
)
BROKEN_ALTERNATE_PROOF_STORE = ArchitectureReductionCase(
    "broken_alternate_proof_store",
    reduction_proof_store_is_canonical=False,
)
BROKEN_REPARSE_PROOF_STORE = ArchitectureReductionCase(
    "broken_reparse_proof_store",
    reduction_proof_store_is_confined_non_reparse=False,
)
BROKEN_REWRAPPED_REDUCTION_PROOF = ArchitectureReductionCase(
    "broken_rewrapped_reduction_proof",
    reduction_proof_execution_unique_per_candidate=False,
)
BROKEN_REVIEW_CURRENTNESS_WINDOW = ArchitectureReductionCase(
    "broken_review_currentness_window",
    reduction_review_final_currentness_rechecked=False,
)
BROKEN_CALLER_AUTHORED_FACADE = ArchitectureReductionCase(
    "broken_caller_authored_facade",
    facade_evidence_derived_from_current_authorities=False,
)
BROKEN_AMBIGUOUS_SHORT_CALLER = ArchitectureReductionCase(
    "broken_ambiguous_short_caller",
    caller_edges_canonical_and_unambiguous=False,
)
BROKEN_CONFLICTING_MEMBER_ACTIONS = ArchitectureReductionCase(
    "broken_conflicting_member_actions",
    conflicting_member_actions_have_unique_primary=False,
)
BROKEN_FINAL_BLUEPRINT_NOT_REBUILT = ArchitectureReductionCase(
    "broken_final_blueprint_not_rebuilt",
    final_blueprint_denominator_rebuilt=False,
)
BROKEN_REVIEW_EXECUTES_PROOF = ArchitectureReductionCase(
    "broken_review_executes_proof",
    review_and_proof_execution_are_separate=False,
)
BROKEN_AUDIT_DISCOVERS_NONCANONICAL_AGGREGATE = ArchitectureReductionCase(
    "broken_audit_discovers_noncanonical_aggregate",
    audit_auto_discovery_one_exact_current_canonical_aggregate=False,
)
BROKEN_IMPLICIT_UNBOUNDED_PROOF_BATCH_REUSE = ArchitectureReductionCase(
    "broken_implicit_unbounded_proof_batch_reuse",
    audit_proof_batch_reuse_explicit_finite=False,
)
BROKEN_INJECTED_PROOF_REGISTRY = ArchitectureReductionCase(
    "broken_injected_proof_registry",
    audit_injected_registry_rejected=False,
)
BROKEN_STALE_PROOF_HISTORY_SELECTED = ArchitectureReductionCase(
    "broken_stale_proof_history_selected",
    audit_stale_history_ignored=False,
)
BROKEN_DUPLICATE_CURRENT_AGGREGATE_PROOF = ArchitectureReductionCase(
    "broken_duplicate_current_aggregate_proof",
    audit_duplicate_current_aggregate_blocked=False,
)
BROKEN_OPAQUE_CANONICAL_RELATION_PROVENANCE = ArchitectureReductionCase(
    "broken_opaque_canonical_relation_provenance",
    canonical_relation_provenance_materialized=False,
)
BROKEN_STALE_FACADE_DELEGATION = ArchitectureReductionCase(
    "broken_stale_facade_delegation",
    facade_delegation_current=False,
)
BROKEN_FACADE_PARALLEL_SUCCESS = ArchitectureReductionCase(
    "broken_facade_parallel_success",
    facade_has_no_independent_success=False,
)
BROKEN_REPEATED_CALLER_SCAN = ArchitectureReductionCase(
    "broken_repeated_caller_scan",
    caller_relations_indexed_once=False,
)
BROKEN_DUPLICATE_SELF_BLUEPRINT_BUILD = ArchitectureReductionCase(
    "broken_duplicate_self_blueprint_build",
    self_maintenance_blueprint_built_once=False,
)
BROKEN_COMPACT_FULL_EXPANSION = ArchitectureReductionCase(
    "broken_compact_full_expansion",
    compact_projection_avoids_full_expansion=False,
)
BROKEN_REPEATED_LARGE_REPORT_FINGERPRINT = ArchitectureReductionCase(
    "broken_repeated_large_report_fingerprint",
    large_immutable_report_fingerprints_cached=False,
)
BROKEN_MATERIALIZED_LARGE_PAYLOAD_FINGERPRINT = ArchitectureReductionCase(
    "broken_materialized_large_payload_fingerprint",
    large_payload_fingerprints_streamed=False,
)
BROKEN_CARTESIAN_CANDIDATE_EVIDENCE = ArchitectureReductionCase(
    "broken_cartesian_candidate_evidence",
    candidate_evidence_neighborhoods_content_addressed_once=False,
)
BROKEN_UNBOUNDED_COMPARISON_CANDIDATE_BATCH = ArchitectureReductionCase(
    "broken_unbounded_comparison_candidate_batch",
    comparison_candidate_batches_finite_and_bounded=False,
)
BROKEN_CANDIDATE_EVIDENCE_REFERENCE = ArchitectureReductionCase(
    "broken_candidate_evidence_reference",
    candidate_evidence_references_exact_and_fail_closed=False,
)
BROKEN_REPEATED_AFFECTED_OBJECT_DENOMINATOR = ArchitectureReductionCase(
    "broken_repeated_affected_object_denominator",
    affected_object_reference_denominator_indexed_once=False,
)
BROKEN_INTERNAL_STEPS_OMITTED = ArchitectureReductionCase(
    "broken_internal_steps_omitted",
    retained_route_internal_steps_classified=False,
)
BROKEN_STEP_ACTION_VOCABULARY = ArchitectureReductionCase(
    "broken_step_action_vocabulary",
    step_action_vocabulary_current=False,
)
BROKEN_STEP_COST_STALE = ArchitectureReductionCase(
    "broken_step_cost_stale",
    step_cost_evidence_current=False,
)
BROKEN_STEP_COST_AS_PROOF = ArchitectureReductionCase(
    "broken_step_cost_as_proof",
    step_cost_is_priority_only=False,
)
BROKEN_UNIQUE_SAFETY_OWNER_REMOVED = ArchitectureReductionCase(
    "broken_unique_safety_owner_removed",
    unique_safety_responsibilities_preserved=False,
)
BROKEN_ON_DEMAND_TRIGGER_IMPLICIT = ArchitectureReductionCase(
    "broken_on_demand_trigger_implicit",
    on_demand_triggers_explicit=False,
)
BROKEN_PROOFLESS_AUDIT_STATUS_CONFLATION = ArchitectureReductionCase(
    "broken_proofless_audit_status_conflation",
    unresolved_candidate_ids=("candidate:proofless",),
    cleanup_release_ready=False,
    review_status="blocked",
)
BROKEN_SAFE_UNAPPLIED_AUDIT_PASS = ArchitectureReductionCase(
    "broken_safe_unapplied_audit_pass",
    action_authorized_candidate_ids=("candidate:safe-unapplied",),
    cleanup_release_ready=False,
    review_status="pass",
)
BROKEN_CLEANUP_READY_WITH_UNRESOLVED = ArchitectureReductionCase(
    "broken_cleanup_ready_with_unresolved",
    unresolved_candidate_ids=("candidate:unresolved",),
    cleanup_release_ready=True,
    review_status="pass",
)
BROKEN_CLEANUP_READY_WITH_UNRESOLVED_STEP = ArchitectureReductionCase(
    "broken_cleanup_ready_with_unresolved_step",
    step_decision_complete=False,
    unresolved_step_ids=("candidate-step:unresolved",),
    cleanup_release_ready=True,
    review_status="pass",
)


class EvaluateArchitectureReductionPlan:
    name = "EvaluateArchitectureReductionPlan"
    reads = ("ArchitectureReductionPolicy",)
    writes = (
        "case_name",
        "existing_model_grounded",
        "observable_contract_declared",
        "code_mapping_present",
        "candidates_classified",
        "proof_status_visible",
        "risky_candidates_kept_visible",
        "public_entrypoint_structuremesh_gate",
        "target_structure_handoff",
        "completed_candidates_not_requeued",
        "companion_route_triggers",
        "no_direct_code_rewrite",
        "validation_gates_visible",
        "reduction_mode",
        "retirement_proof_present",
        "retirement_proof_current",
        "retirement_responsibilities_complete",
        "retirement_replacement_owners_current",
        "retirement_negative_cases_preserved",
        "retirement_has_no_compatibility_survival",
        "ordinary_contraction_behavior_equivalent",
        "expected_candidate_inventory_declared",
        "expected_candidates_materialized",
        "all_reduction_signal_families_dispositioned",
        "self_blueprint_identity_exact_current",
        "retain_and_unresolved_dispositions_independently_evidenced",
        "candidate_signal_dispositions_are_relation_aware",
        "candidate_retain_authority_is_independent",
        "same_commitment_candidates_stay_unresolved",
        "retained_implementation_necessity_witness_current_and_independent",
        "test_and_model_validation_evidence_namespaces_separate",
        "identifier_only_semantic_difference_rejected",
        "public_role_without_promise_rejected",
        "external_promise_exact_model_code_test_binding",
        "maintenance_lexical_name_is_signal_only",
        "maintenance_candidate_requires_exact_related_multi_surface",
        "reduction_proofs_independently_verified",
        "reduction_proofs_use_executed_child_receipts",
        "candidate_tests_are_semantically_executed",
        "parity_replays_bound_behavior_oracles",
        "reduction_proof_store_is_canonical",
        "reduction_proof_store_is_confined_non_reparse",
        "reduction_proof_execution_unique_per_candidate",
        "facade_evidence_derived_from_current_authorities",
        "caller_edges_canonical_and_unambiguous",
        "conflicting_member_actions_have_unique_primary",
        "reduction_review_final_currentness_rechecked",
        "final_blueprint_denominator_rebuilt",
        "review_and_proof_execution_are_separate",
        "audit_auto_discovery_one_exact_current_canonical_aggregate",
        "audit_proof_batch_reuse_explicit_finite",
        "audit_injected_registry_rejected",
        "audit_stale_history_ignored",
        "audit_duplicate_current_aggregate_blocked",
        "canonical_relation_provenance_materialized",
        "facade_delegation_current",
        "facade_has_no_independent_success",
        "caller_relations_indexed_once",
        "self_maintenance_blueprint_built_once",
        "compact_projection_avoids_full_expansion",
        "large_immutable_report_fingerprints_cached",
        "large_payload_fingerprints_streamed",
        "candidate_evidence_neighborhoods_content_addressed_once",
        "comparison_candidate_batches_finite_and_bounded",
        "candidate_evidence_references_exact_and_fail_closed",
        "affected_object_reference_denominator_indexed_once",
        "retained_route_internal_steps_classified",
        "step_action_vocabulary_current",
        "step_cost_evidence_current",
        "step_cost_is_priority_only",
        "unique_safety_responsibilities_preserved",
        "on_demand_triggers_explicit",
        "audit_complete",
        "step_decision_complete",
        "action_authorized_candidate_ids",
        "unresolved_candidate_ids",
        "unresolved_step_ids",
        "cleanup_release_ready",
        "review_status",
    )
    accepted_input_type = ArchitectureReductionCase
    input_description = "architecture reduction route case"
    output_description = "architecture reduction governance policy"
    idempotency = "same case produces one policy state"

    def apply(self, input_obj: ArchitectureReductionCase, _state: ArchitectureReductionPolicy):
        new_state = ArchitectureReductionPolicy(
            case_name=input_obj.name,
            existing_model_grounded=input_obj.existing_model_grounded,
            observable_contract_declared=input_obj.observable_contract_declared,
            code_mapping_present=input_obj.code_mapping_present,
            candidates_classified=input_obj.candidates_classified,
            proof_status_visible=input_obj.proof_status_visible,
            risky_candidates_kept_visible=input_obj.risky_candidates_kept_visible,
            public_entrypoint_structuremesh_gate=input_obj.public_entrypoint_structuremesh_gate,
            target_structure_handoff=input_obj.target_structure_handoff,
            completed_candidates_not_requeued=input_obj.completed_candidates_not_requeued,
            companion_route_triggers=input_obj.companion_route_triggers,
            no_direct_code_rewrite=input_obj.no_direct_code_rewrite,
            validation_gates_visible=input_obj.validation_gates_visible,
            reduction_mode=input_obj.reduction_mode,
            retirement_proof_present=input_obj.retirement_proof_present,
            retirement_proof_current=input_obj.retirement_proof_current,
            retirement_responsibilities_complete=(
                input_obj.retirement_responsibilities_complete
            ),
            retirement_replacement_owners_current=(
                input_obj.retirement_replacement_owners_current
            ),
            retirement_negative_cases_preserved=(
                input_obj.retirement_negative_cases_preserved
            ),
            retirement_has_no_compatibility_survival=(
                input_obj.retirement_has_no_compatibility_survival
            ),
            ordinary_contraction_behavior_equivalent=(
                input_obj.ordinary_contraction_behavior_equivalent
            ),
            expected_candidate_inventory_declared=input_obj.expected_candidate_inventory_declared,
            expected_candidates_materialized=input_obj.expected_candidates_materialized,
            all_reduction_signal_families_dispositioned=input_obj.all_reduction_signal_families_dispositioned,
            self_blueprint_identity_exact_current=(
                input_obj.self_blueprint_identity_exact_current
            ),
            retain_and_unresolved_dispositions_independently_evidenced=(
                input_obj.retain_and_unresolved_dispositions_independently_evidenced
            ),
            candidate_signal_dispositions_are_relation_aware=(
                input_obj.candidate_signal_dispositions_are_relation_aware
            ),
            candidate_retain_authority_is_independent=(
                input_obj.candidate_retain_authority_is_independent
            ),
            same_commitment_candidates_stay_unresolved=(
                input_obj.same_commitment_candidates_stay_unresolved
            ),
            retained_implementation_necessity_witness_current_and_independent=(
                input_obj.retained_implementation_necessity_witness_current_and_independent
            ),
            test_and_model_validation_evidence_namespaces_separate=(
                input_obj.test_and_model_validation_evidence_namespaces_separate
            ),
            identifier_only_semantic_difference_rejected=(
                input_obj.identifier_only_semantic_difference_rejected
            ),
            public_role_without_promise_rejected=(
                input_obj.public_role_without_promise_rejected
            ),
            external_promise_exact_model_code_test_binding=(
                input_obj.external_promise_exact_model_code_test_binding
            ),
            maintenance_lexical_name_is_signal_only=(
                input_obj.maintenance_lexical_name_is_signal_only
            ),
            maintenance_candidate_requires_exact_related_multi_surface=(
                input_obj.maintenance_candidate_requires_exact_related_multi_surface
            ),
            reduction_proofs_independently_verified=(
                input_obj.reduction_proofs_independently_verified
            ),
            reduction_proofs_use_executed_child_receipts=(
                input_obj.reduction_proofs_use_executed_child_receipts
            ),
            candidate_tests_are_semantically_executed=(
                input_obj.candidate_tests_are_semantically_executed
            ),
            parity_replays_bound_behavior_oracles=(
                input_obj.parity_replays_bound_behavior_oracles
            ),
            reduction_proof_store_is_canonical=(
                input_obj.reduction_proof_store_is_canonical
            ),
            reduction_proof_store_is_confined_non_reparse=(
                input_obj.reduction_proof_store_is_confined_non_reparse
            ),
            reduction_proof_execution_unique_per_candidate=(
                input_obj.reduction_proof_execution_unique_per_candidate
            ),
            facade_evidence_derived_from_current_authorities=(
                input_obj.facade_evidence_derived_from_current_authorities
            ),
            caller_edges_canonical_and_unambiguous=(
                input_obj.caller_edges_canonical_and_unambiguous
            ),
            conflicting_member_actions_have_unique_primary=(
                input_obj.conflicting_member_actions_have_unique_primary
            ),
            reduction_review_final_currentness_rechecked=(
                input_obj.reduction_review_final_currentness_rechecked
            ),
            final_blueprint_denominator_rebuilt=(
                input_obj.final_blueprint_denominator_rebuilt
            ),
            review_and_proof_execution_are_separate=(
                input_obj.review_and_proof_execution_are_separate
            ),
            audit_auto_discovery_one_exact_current_canonical_aggregate=(
                input_obj.audit_auto_discovery_one_exact_current_canonical_aggregate
            ),
            audit_proof_batch_reuse_explicit_finite=(
                input_obj.audit_proof_batch_reuse_explicit_finite
            ),
            audit_injected_registry_rejected=(
                input_obj.audit_injected_registry_rejected
            ),
            audit_stale_history_ignored=input_obj.audit_stale_history_ignored,
            audit_duplicate_current_aggregate_blocked=(
                input_obj.audit_duplicate_current_aggregate_blocked
            ),
            canonical_relation_provenance_materialized=input_obj.canonical_relation_provenance_materialized,
            facade_delegation_current=input_obj.facade_delegation_current,
            facade_has_no_independent_success=input_obj.facade_has_no_independent_success,
            caller_relations_indexed_once=input_obj.caller_relations_indexed_once,
            self_maintenance_blueprint_built_once=(
                input_obj.self_maintenance_blueprint_built_once
            ),
            compact_projection_avoids_full_expansion=(
                input_obj.compact_projection_avoids_full_expansion
            ),
            large_immutable_report_fingerprints_cached=(
                input_obj.large_immutable_report_fingerprints_cached
            ),
            large_payload_fingerprints_streamed=(
                input_obj.large_payload_fingerprints_streamed
            ),
            candidate_evidence_neighborhoods_content_addressed_once=(
                input_obj.candidate_evidence_neighborhoods_content_addressed_once
            ),
            comparison_candidate_batches_finite_and_bounded=(
                input_obj.comparison_candidate_batches_finite_and_bounded
            ),
            candidate_evidence_references_exact_and_fail_closed=(
                input_obj.candidate_evidence_references_exact_and_fail_closed
            ),
            affected_object_reference_denominator_indexed_once=(
                input_obj.affected_object_reference_denominator_indexed_once
            ),
            retained_route_internal_steps_classified=(
                input_obj.retained_route_internal_steps_classified
            ),
            step_action_vocabulary_current=(
                input_obj.step_action_vocabulary_current
            ),
            step_cost_evidence_current=input_obj.step_cost_evidence_current,
            step_cost_is_priority_only=input_obj.step_cost_is_priority_only,
            unique_safety_responsibilities_preserved=(
                input_obj.unique_safety_responsibilities_preserved
            ),
            on_demand_triggers_explicit=input_obj.on_demand_triggers_explicit,
            audit_complete=input_obj.audit_complete,
            step_decision_complete=input_obj.step_decision_complete,
            action_authorized_candidate_ids=(
                input_obj.action_authorized_candidate_ids
            ),
            unresolved_candidate_ids=input_obj.unresolved_candidate_ids,
            unresolved_step_ids=input_obj.unresolved_step_ids,
            cleanup_release_ready=input_obj.cleanup_release_ready,
            review_status=input_obj.review_status,
        )
        return (
            FunctionResult(
                output=input_obj,
                new_state=new_state,
                label=input_obj.name,
                reason="projected architecture reduction route decision into policy state",
            ),
        )


def _pass() -> InvariantResult:
    return InvariantResult.pass_()


def _fail(name: str, message: str) -> InvariantResult:
    return InvariantResult.fail(message, {"violation": name})


def _empty(state: ArchitectureReductionPolicy) -> bool:
    return not state.case_name


def existing_model_is_grounded(state: ArchitectureReductionPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.existing_model_grounded:
        return _fail("existing_model_is_grounded", "architecture reduction must reuse or inspect existing model ownership first")
    return _pass()


def observable_contract_exists(state: ArchitectureReductionPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.observable_contract_declared:
        return _fail("observable_contract_exists", "code contraction needs an explicit observable behavior boundary")
    return _pass()


def code_mapping_exists(state: ArchitectureReductionPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.code_mapping_present:
        return _fail("code_mapping_exists", "model reduction must map to code nodes before recommending contraction")
    return _pass()


def candidates_and_proofs_are_visible(state: ArchitectureReductionPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.candidates_classified:
        return _fail("candidates_and_proofs_are_visible", "reduction candidates are not classified")
    if not state.proof_status_visible:
        return _fail("candidates_and_proofs_are_visible", "candidate proof status is hidden")
    return _pass()


def risky_candidates_are_not_deleted_silently(state: ArchitectureReductionPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.risky_candidates_kept_visible:
        return _fail("risky_candidates_are_not_deleted_silently", "risky duplicate-looking branches must stay visible")
    return _pass()


def public_entrypoints_use_structuremesh_gate(state: ArchitectureReductionPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.public_entrypoint_structuremesh_gate:
        return _fail(
            "public_entrypoints_use_structuremesh_gate",
            "public entrypoint contractions must go through StructureMesh or equivalent parity gate",
        )
    return _pass()


def target_structure_handoff_exists(state: ArchitectureReductionPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.target_structure_handoff:
        return _fail("target_structure_handoff_exists", "reduced model must hand off target structure recommendations")
    return _pass()


def completed_candidates_leave_active_queue(state: ArchitectureReductionPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.completed_candidates_not_requeued:
        return _fail(
            "completed_candidates_leave_active_queue",
            "completed or historical candidates need evidence but must not stay in ready work",
        )
    return _pass()


def companion_route_triggers_exist(state: ArchitectureReductionPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.companion_route_triggers:
        return _fail("companion_route_triggers_exist", "related skills need complexity-growth triggers")
    return _pass()


def architecture_reduction_does_not_rewrite_code(state: ArchitectureReductionPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.no_direct_code_rewrite:
        return _fail("architecture_reduction_does_not_rewrite_code", "architecture reduction must not rewrite production code directly")
    return _pass()


def validation_gates_remain_visible(state: ArchitectureReductionPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.validation_gates_visible:
        return _fail("validation_gates_remain_visible", "tests, conformance, and StructureMesh gates must remain visible")
    return _pass()


def behavior_change_requires_complete_current_retirement_proof(
    state: ArchitectureReductionPolicy,
    _trace: object,
) -> InvariantResult:
    if _empty(state):
        return _pass()
    if state.reduction_mode != "retire_behavior":
        if state.retirement_proof_present:
            return _fail(
                "behavior_change_requires_complete_current_retirement_proof",
                "ordinary equivalence contraction cannot carry retirement authority",
            )
        if not state.ordinary_contraction_behavior_equivalent:
            return _fail(
                "behavior_change_requires_complete_current_retirement_proof",
                "ordinary contraction must preserve observable behavior",
            )
        return _pass()
    if not state.retirement_proof_present or not state.retirement_proof_current:
        return _fail(
            "behavior_change_requires_complete_current_retirement_proof",
            "intentional behavior retirement requires one complete exact-current proof",
        )
    if not state.retirement_responsibilities_complete:
        return _fail(
            "behavior_change_requires_complete_current_retirement_proof",
            "retirement must disposition every code, model, test, route, public surface, consumer, prompt, skill, topology, release, and negative-case responsibility",
        )
    if not state.retirement_replacement_owners_current:
        return _fail(
            "behavior_change_requires_complete_current_retirement_proof",
            "every still-required protection needs one exact current replacement owner",
        )
    if not state.retirement_negative_cases_preserved:
        return _fail(
            "behavior_change_requires_complete_current_retirement_proof",
            "retirement cannot orphan a required rejection rule, negative case, or oracle",
        )
    if not state.retirement_has_no_compatibility_survival:
        return _fail(
            "behavior_change_requires_complete_current_retirement_proof",
            "retired behavior cannot survive through alias, compatibility, forwarder, fallback, or current runtime authority",
        )
    return _pass()


def expected_candidate_inventory_is_complete(state: ArchitectureReductionPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.expected_candidate_inventory_declared:
        return _fail(
            "expected_candidate_inventory_is_complete",
            "candidate completeness requires an independently declared expected inventory",
        )
    if not state.expected_candidates_materialized:
        return _fail(
            "expected_candidate_inventory_is_complete",
            "an expected reduction candidate is omitted without a scoped disposition",
        )
    if not state.all_reduction_signal_families_dispositioned:
        return _fail(
            "expected_candidate_inventory_is_complete",
            "route, branch, adapter, wrapper/facade, helper, validation, size, and repeated-shape signals require retain, contract, or unresolved dispositions",
        )
    return _pass()


def retained_route_steps_use_evidence_bound_actions(
    state: ArchitectureReductionPolicy,
    _trace: object,
) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.retained_route_internal_steps_classified:
        return _fail(
            "retained_route_steps_use_evidence_bound_actions",
            "a retained route was reviewed as one box while its scans, reflections, evidence projections, serializers, payload builders, validations, branches, or helpers were omitted",
        )
    if not state.step_action_vocabulary_current:
        return _fail(
            "retained_route_steps_use_evidence_bound_actions",
            "internal steps must use exactly retain, merge, delegate, remove, explicit_on_demand, or unresolved",
        )
    if not state.step_cost_evidence_current:
        return _fail(
            "retained_route_steps_use_evidence_bound_actions",
            "an internal-step decision lacks current operation-count or payload-size evidence",
        )
    if not state.step_cost_is_priority_only:
        return _fail(
            "retained_route_steps_use_evidence_bound_actions",
            "high operation, payload, or token cost was treated as contraction proof instead of review priority only",
        )
    if not state.unique_safety_responsibilities_preserved:
        return _fail(
            "retained_route_steps_use_evidence_bound_actions",
            "a merge, delegation, removal, or on-demand action erased the only safety or evidence owner without an exact current replacement",
        )
    if not state.on_demand_triggers_explicit:
        return _fail(
            "retained_route_steps_use_evidence_bound_actions",
            "an expensive step was made on-demand without one explicit trigger boundary",
        )
    return _pass()


def self_reduction_claim_is_independently_evidence_bound(
    state: ArchitectureReductionPolicy,
    _trace: object,
) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.self_blueprint_identity_exact_current:
        return _fail(
            "self_reduction_claim_is_independently_evidence_bound",
            "self-reduction accepted a label-only or stale self-blueprint instead of the exact current typed blueprint",
        )
    if not state.retain_and_unresolved_dispositions_independently_evidenced:
        return _fail(
            "self_reduction_claim_is_independently_evidence_bound",
            "an unresolved member was automatically rewritten as retained without an independent terminal disposition",
        )
    if not state.candidate_signal_dispositions_are_relation_aware:
        return _fail(
            "self_reduction_claim_is_independently_evidence_bound",
            "a contraction-candidate signal was retained from source existence instead of candidate-specific different-contract or equivalence evidence",
        )
    if not state.candidate_retain_authority_is_independent:
        return _fail(
            "self_reduction_claim_is_independently_evidence_bound",
            "a candidate binding or its own fingerprint was allowed to prove that the candidate must be retained",
        )
    if not state.same_commitment_candidates_stay_unresolved:
        return _fail(
            "self_reduction_claim_is_independently_evidence_bound",
            "structurally similar members with the same current behavior commitment were retained without equivalence, facade, on-demand, or retirement proof",
        )
    if not state.reduction_proofs_independently_verified:
        return _fail(
            "self_reduction_claim_is_independently_evidence_bound",
            "self-reduction trusted caller-declared proof currentness instead of independently verifying the canonical receipt and current context",
        )
    if not state.reduction_proofs_use_executed_child_receipts:
        return _fail(
            "self_reduction_claim_is_independently_evidence_bound",
            "a caller-authored passing leaf replaced supervised candidate test and parity child executions",
        )
    if not state.candidate_tests_are_semantically_executed:
        return _fail(
            "self_reduction_claim_is_independently_evidence_bound",
            "candidate test authority used exit zero without exact collection, pass, skip, xfail, deselection, and executed-oracle evidence",
        )
    if not state.parity_replays_bound_behavior_oracles:
        return _fail(
            "self_reduction_claim_is_independently_evidence_bound",
            "candidate parity checked metadata labels instead of executing every affected member and its input/output/state/effect/error oracle",
        )
    if not state.reduction_proof_store_is_canonical:
        return _fail(
            "self_reduction_claim_is_independently_evidence_bound",
            "an alternate caller-selected receipt store was treated as current contraction authority",
        )
    if not state.reduction_proof_store_is_confined_non_reparse:
        return _fail(
            "self_reduction_claim_is_independently_evidence_bound",
            "the canonical proof store or proof artifact may escape through a symlink, junction, reparse point, or repository-external path",
        )
    if not state.reduction_proof_execution_unique_per_candidate:
        return _fail(
            "self_reduction_claim_is_independently_evidence_bound",
            "different candidates reused one proof artifact, result, or execution identity through distinct wrappers",
        )
    if not state.facade_evidence_derived_from_current_authorities:
        return _fail(
            "self_reduction_claim_is_independently_evidence_bound",
            "public-facade delegation facts were supplied by the proof caller instead of derived from the current ledger and code binding",
        )
    if not state.caller_edges_canonical_and_unambiguous:
        return _fail(
            "self_reduction_claim_is_independently_evidence_bound",
            "short-name or receiver-qualified caller parsing silently merged or discarded an ambiguous target instead of producing canonical surface-id edges or an explicit gap",
        )
    if not state.conflicting_member_actions_have_unique_primary:
        return _fail(
            "self_reduction_claim_is_independently_evidence_bound",
            "one code member received conflicting candidate actions without one independently selected primary candidate",
        )
    if not state.reduction_review_final_currentness_rechecked:
        return _fail(
            "self_reduction_claim_is_independently_evidence_bound",
            "governed source or proof inputs were not rechecked immediately before publishing the cleanup result",
        )
    if not state.final_blueprint_denominator_rebuilt:
        return _fail(
            "self_reduction_claim_is_independently_evidence_bound",
            "the review did not rebuild and compare a fresh self blueprint and reduction denominator immediately before publication",
        )
    if not state.review_and_proof_execution_are_separate:
        return _fail(
            "self_reduction_claim_is_independently_evidence_bound",
            "the read-only review path can start proof commands instead of consuming only explicitly executed canonical proof artifacts",
        )
    return _pass()


def retained_implementation_requires_semantic_necessity(
    state: ArchitectureReductionPolicy,
    _trace: object,
) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.retained_implementation_necessity_witness_current_and_independent:
        return _fail(
            "retained_implementation_requires_semantic_necessity",
            "a retained implementation lacks one candidate-independent exact-current necessity witness",
        )
    if not state.test_and_model_validation_evidence_namespaces_separate:
        return _fail(
            "retained_implementation_requires_semantic_necessity",
            "ordinary test nodes and model-regression evidence were mixed into one inventory namespace instead of being independently validated and jointly bound",
        )
    if not state.identifier_only_semantic_difference_rejected:
        return _fail(
            "retained_implementation_requires_semantic_necessity",
            "structure, owner, model, spec, oracle, test, receipt, or candidate identities were treated as semantic difference without an independent necessity witness",
        )
    if not state.external_promise_exact_model_code_test_binding:
        return _fail(
            "retained_implementation_requires_semantic_necessity",
            "an external promise was accepted without one current BCL review binding its exact primary model, the same blueprint owner contract, and current test evidence",
        )
    return _pass()


def public_role_is_not_a_current_promise(
    state: ArchitectureReductionPolicy,
    _trace: object,
) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.public_role_without_promise_rejected:
        return _fail(
            "public_role_is_not_a_current_promise",
            "a public role label was treated as a current product promise without one exact-current behavior commitment or public contract",
        )
    return _pass()


def maintenance_lexical_signal_requires_exact_relation(
    state: ArchitectureReductionPolicy,
    _trace: object,
) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.maintenance_lexical_name_is_signal_only:
        return _fail(
            "maintenance_lexical_signal_requires_exact_relation",
            "an isolated fallback, alias, compat, legacy, or deprecated lexical name materialized a candidate instead of remaining a signal",
        )
    if not state.maintenance_candidate_requires_exact_related_multi_surface:
        return _fail(
            "maintenance_lexical_signal_requires_exact_relation",
            "a maintenance-like candidate materialized without one exact related multi-surface relation",
        )
    return _pass()


def read_only_audit_uses_one_current_aggregate_proof(
    state: ArchitectureReductionPolicy,
    _trace: object,
) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.audit_auto_discovery_one_exact_current_canonical_aggregate:
        return _fail(
            "read_only_audit_uses_one_current_aggregate_proof",
            "read-only audit auto-discovery admitted something other than one exact-current canonical aggregate proof",
        )
    if not state.audit_proof_batch_reuse_explicit_finite:
        return _fail(
            "read_only_audit_uses_one_current_aggregate_proof",
            "proof production or reuse was implicit or unbounded instead of one explicit finite batch",
        )
    if not state.audit_injected_registry_rejected:
        return _fail(
            "read_only_audit_uses_one_current_aggregate_proof",
            "the read-only audit accepted a caller-injected proof registry",
        )
    if not state.audit_stale_history_ignored:
        return _fail(
            "read_only_audit_uses_one_current_aggregate_proof",
            "stale historical proof was selected as current aggregate authority",
        )
    if not state.audit_duplicate_current_aggregate_blocked:
        return _fail(
            "read_only_audit_uses_one_current_aggregate_proof",
            "multiple exact-current aggregate proofs were accepted instead of blocking duplicate authority",
        )
    return _pass()


def canonical_relation_provenance_is_materialized(state: ArchitectureReductionPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.canonical_relation_provenance_materialized:
        return _fail(
            "canonical_relation_provenance_is_materialized",
            "canonical relation and code-obligation ids must bind concrete candidates and target actions",
        )
    return _pass()


def retained_facades_delegate_only(state: ArchitectureReductionPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.facade_delegation_current:
        return _fail(
            "retained_facades_delegate_only",
            "retained facade lacks current proof of delegation to the selected primary path",
        )
    if not state.facade_has_no_independent_success:
        return _fail(
            "retained_facades_delegate_only",
            "retained facade still owns an independent success or primary side effect",
        )
    return _pass()


def self_reduction_execution_is_single_pass(
    state: ArchitectureReductionPolicy,
    _trace: object,
) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.caller_relations_indexed_once:
        return _fail(
            "self_reduction_execution_is_single_pass",
            "self-reduction must index governed caller relations once instead of rescanning all surfaces per candidate member",
        )
    if not state.self_maintenance_blueprint_built_once:
        return _fail(
            "self_reduction_execution_is_single_pass",
            "composed self-maintenance must pass one exact in-memory self-blueprint to both bounded reviews",
        )
    if not state.compact_projection_avoids_full_expansion:
        return _fail(
            "self_reduction_execution_is_single_pass",
            "compact self-maintenance must project bounded fields directly instead of expanding and discarding the complete blueprint or reduction payload",
        )
    if not state.large_immutable_report_fingerprints_cached:
        return _fail(
            "self_reduction_execution_is_single_pass",
            "immutable large behavior evidence must reuse its exact fingerprint instead of rebuilding the complete payload for every consumer",
        )
    if not state.large_payload_fingerprints_streamed:
        return _fail(
            "self_reduction_execution_is_single_pass",
            "large canonical payloads must stream fingerprint and size computation instead of retaining several complete serialized copies",
        )
    if not state.candidate_evidence_neighborhoods_content_addressed_once:
        return _fail(
            "self_reduction_execution_is_single_pass",
            "shared candidate test and coverage neighborhoods must be content-addressed once instead of expanded for every candidate",
        )
    if not state.comparison_candidate_batches_finite_and_bounded:
        return _fail(
            "self_reduction_execution_is_single_pass",
            "comparison and unreferenced-helper signals must be partitioned into deterministic finite batches instead of expanding one unbounded cleanup candidate",
        )
    if not state.candidate_evidence_references_exact_and_fail_closed:
        return _fail(
            "self_reduction_execution_is_single_pass",
            "candidate evidence references must resolve one exact current neighborhood and reject missing, stale, foreign, duplicated, or inline-fallback evidence",
        )
    if not state.affected_object_reference_denominator_indexed_once:
        return _fail(
            "self_reduction_execution_is_single_pass",
            "affected-object references must reuse one exact validated object-id denominator instead of rebuilding it for every affected or topology edge",
        )
    return _pass()


def audit_completion_is_distinct_from_cleanup_authorization(
    state: ArchitectureReductionPolicy,
    _trace: object,
) -> InvariantResult:
    if _empty(state):
        return _pass()
    authorized = tuple(state.action_authorized_candidate_ids)
    unresolved = tuple(state.unresolved_candidate_ids)
    unresolved_steps = tuple(state.unresolved_step_ids)
    if len(set(authorized)) != len(authorized) or len(set(unresolved)) != len(
        unresolved
    ) or len(set(unresolved_steps)) != len(unresolved_steps):
        return _fail(
            "audit_completion_is_distinct_from_cleanup_authorization",
            "audit, action, and unresolved candidate identities must be exact unique sets",
        )
    if set(authorized) & set(unresolved):
        return _fail(
            "audit_completion_is_distinct_from_cleanup_authorization",
            "one candidate cannot be both action-authorized and unresolved",
        )
    if authorized and not state.audit_complete:
        return _fail(
            "audit_completion_is_distinct_from_cleanup_authorization",
            "candidate action authorization requires a complete current audit",
        )
    if state.step_decision_complete and unresolved_steps:
        return _fail(
            "audit_completion_is_distinct_from_cleanup_authorization",
            "step-decision completion cannot coexist with unresolved internal-step identities",
        )
    if not state.step_decision_complete and not unresolved_steps:
        return _fail(
            "audit_completion_is_distinct_from_cleanup_authorization",
            "an incomplete step decision must name the exact unresolved internal steps",
        )
    if state.cleanup_release_ready and (
        not state.audit_complete
        or not state.step_decision_complete
        or authorized
        or unresolved
        or unresolved_steps
    ):
        return _fail(
            "audit_completion_is_distinct_from_cleanup_authorization",
            "cleanup readiness requires a complete audit and complete step decisions with zero unresolved or authorized-but-unapplied actions",
        )
    expected_status = (
        "pass" if state.audit_complete and not authorized else "blocked"
    )
    if state.review_status != expected_status:
        return _fail(
            "audit_completion_is_distinct_from_cleanup_authorization",
            "review status conflated audit completion with cleanup readiness or ignored an authorized-but-unapplied action",
        )
    return _pass()


INVARIANTS = (
    Invariant(
        "existing_model_is_grounded",
        "Architecture reduction starts from existing model ownership.",
        existing_model_is_grounded,
    ),
    Invariant(
        "observable_contract_exists",
        "Architecture reduction declares what public behavior must stay unchanged.",
        observable_contract_exists,
    ),
    Invariant(
        "code_mapping_exists",
        "Model reduction is mapped back to code nodes before code contraction is suggested.",
        code_mapping_exists,
    ),
    Invariant(
        "candidates_and_proofs_are_visible",
        "Reduction candidates and proof status stay explicit.",
        candidates_and_proofs_are_visible,
    ),
    Invariant(
        "risky_candidates_are_not_deleted_silently",
        "Risky candidates remain visible instead of being treated as safe deletes.",
        risky_candidates_are_not_deleted_silently,
    ),
    Invariant(
        "public_entrypoints_use_structuremesh_gate",
        "Public entrypoint changes require StructureMesh or equivalent parity evidence.",
        public_entrypoints_use_structuremesh_gate,
    ),
    Invariant(
        "target_structure_handoff_exists",
        "Reduced model evidence feeds target code structure planning.",
        target_structure_handoff_exists,
    ),
    Invariant(
        "completed_candidates_leave_active_queue",
        "Completed candidates stay visible without being re-queued as ready work.",
        completed_candidates_leave_active_queue,
    ),
    Invariant(
        "companion_route_triggers_exist",
        "Related FlowGuard skills know when to invoke architecture reduction.",
        companion_route_triggers_exist,
    ),
    Invariant(
        "architecture_reduction_does_not_rewrite_code",
        "Architecture reduction reviews and hands off instead of rewriting code directly.",
        architecture_reduction_does_not_rewrite_code,
    ),
    Invariant(
        "validation_gates_remain_visible",
        "Refactor validation gates remain visible before completion claims.",
        validation_gates_remain_visible,
    ),
    Invariant(
        "behavior_change_requires_complete_current_retirement_proof",
        "Behavior changes are allowed only through a complete current retirement proof; ordinary contraction remains behavior-preserving.",
        behavior_change_requires_complete_current_retirement_proof,
    ),
    Invariant(
        "expected_candidate_inventory_is_complete",
        "Expected candidate inventory is independent, current, and fully dispositioned.",
        expected_candidate_inventory_is_complete,
    ),
    Invariant(
        "retained_route_steps_use_evidence_bound_actions",
        "Retained-route internal steps have typed necessity, current cost, equivalence, and safety-owner decisions.",
        retained_route_steps_use_evidence_bound_actions,
    ),
    Invariant(
        "self_reduction_claim_is_independently_evidence_bound",
        "Self-reduction consumes one exact current typed blueprint and independently evidenced dispositions and proofs.",
        self_reduction_claim_is_independently_evidence_bound,
    ),
    Invariant(
        "retained_implementation_requires_semantic_necessity",
        "Retained implementation needs one current candidate-independent semantic necessity witness; identifiers alone create no difference.",
        retained_implementation_requires_semantic_necessity,
    ),
    Invariant(
        "public_role_is_not_a_current_promise",
        "A public role label alone does not establish one current product promise.",
        public_role_is_not_a_current_promise,
    ),
    Invariant(
        "maintenance_lexical_signal_requires_exact_relation",
        "A maintenance-like lexical name remains a signal unless an exact related multi-surface relation materializes a candidate.",
        maintenance_lexical_signal_requires_exact_relation,
    ),
    Invariant(
        "read_only_audit_uses_one_current_aggregate_proof",
        "Read-only audit discovers only one exact-current canonical aggregate proof; batches are explicit and duplicate authority blocks.",
        read_only_audit_uses_one_current_aggregate_proof,
    ),
    Invariant(
        "canonical_relation_provenance_is_materialized",
        "Canonical relation handoffs bind concrete reduction candidates and target actions.",
        canonical_relation_provenance_is_materialized,
    ),
    Invariant(
        "retained_facades_delegate_only",
        "Retained facades have current delegation proof and no independent authority.",
        retained_facades_delegate_only,
    ),
    Invariant(
        "self_reduction_execution_is_single_pass",
        "Self-maintenance builds one blueprint and indexes caller relations once.",
        self_reduction_execution_is_single_pass,
    ),
    Invariant(
        "audit_completion_is_distinct_from_cleanup_authorization",
        "Audit completion, action authorization, and cleanup readiness remain separate claims.",
        audit_completion_is_distinct_from_cleanup_authorization,
    ),
)


def build_workflow() -> Workflow:
    return Workflow((EvaluateArchitectureReductionPlan(),), name="architecture_reduction_rollout")


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
    case: ArchitectureReductionCase,
    expected: ScenarioExpectation,
) -> Scenario:
    return Scenario(
        name=name,
        description=description,
        workflow=build_workflow(),
        initial_state=ArchitectureReductionPolicy(),
        external_input_sequence=(case,),
        invariants=INVARIANTS,
        expected=expected,
    )


SCENARIOS = (
    scenario(
        "good_plan_passes",
        "A complete architecture reduction route plan passes.",
        GOOD_PLAN,
        _expect_ok("complete architecture reduction plan passes", labels=("good_architecture_reduction_plan",)),
    ),
    scenario(
        "good_intentional_retirement_passes",
        "A complete current retirement proof may deliberately end obsolete behavior.",
        GOOD_RETIREMENT_PLAN,
        _expect_ok(
            "complete intentional retirement proof passes",
            labels=("good_intentional_retirement_plan",),
        ),
    ),
    scenario(
        "proofless_risky_keep_audit_passes",
        "A complete audit may pass while a proofless candidate remains unresolved and cleanup stays not ready.",
        PROOFLESS_RISKY_KEEP_PLAN,
        _expect_ok(
            "proofless risky-keep audit passes without cleanup authority",
            labels=("proofless_risky_keep_audit_plan",),
        ),
    ),
    scenario(
        "safe_unapplied_action_is_visible_and_blocked",
        "A complete audit may expose a proof-authorized but unapplied action while the report status remains blocked.",
        SAFE_UNAPPLIED_PLAN,
        _expect_ok(
            "safe unapplied action remains visible and blocks report status",
            labels=("safe_unapplied_action_plan",),
        ),
    ),
    scenario(
        "incomplete_audit_is_visibly_blocked",
        "An incomplete audit remains blocked without cleanup authority.",
        INCOMPLETE_AUDIT_PLAN,
        _expect_ok(
            "incomplete audit combination is represented without false cleanup authority",
            labels=("incomplete_audit_plan",),
        ),
    ),
    scenario(
        "missing_model_grounding_fails",
        "Reduction must inspect existing model ownership first.",
        BROKEN_NO_MODEL_GROUNDING,
        _expect_violation("missing existing model grounding fails", ("existing_model_is_grounded",)),
    ),
    scenario(
        "ordinary_contraction_behavior_change_fails",
        "Ordinary contraction cannot silently change behavior.",
        BROKEN_CONTRACT_CHANGES_BEHAVIOR,
        _expect_violation(
            "ordinary contraction behavior change fails",
            ("behavior_change_requires_complete_current_retirement_proof",),
        ),
    ),
    scenario(
        "retirement_proof_on_contract_fails",
        "Retirement authority cannot be attached to an ordinary equivalence action.",
        BROKEN_RETIREMENT_PROOF_ON_CONTRACT,
        _expect_violation(
            "retirement proof on contract action fails",
            ("behavior_change_requires_complete_current_retirement_proof",),
        ),
    ),
    scenario(
        "missing_retirement_proof_fails",
        "Intentional retirement requires an explicit current proof.",
        BROKEN_RETIREMENT_PROOF_MISSING,
        _expect_violation(
            "missing retirement proof fails",
            ("behavior_change_requires_complete_current_retirement_proof",),
        ),
    ),
    scenario(
        "stale_retirement_proof_fails",
        "Stale retirement evidence cannot authorize behavior change.",
        BROKEN_RETIREMENT_PROOF_STALE,
        _expect_violation(
            "stale retirement proof fails",
            ("behavior_change_requires_complete_current_retirement_proof",),
        ),
    ),
    scenario(
        "retirement_responsibility_gap_fails",
        "Every current responsibility needs one retirement disposition.",
        BROKEN_RETIREMENT_RESPONSIBILITY_GAP,
        _expect_violation(
            "retirement responsibility gap fails",
            ("behavior_change_requires_complete_current_retirement_proof",),
        ),
    ),
    scenario(
        "retirement_ambiguous_replacement_owner_fails",
        "Required protections need exact current replacement owners.",
        BROKEN_RETIREMENT_OWNER_AMBIGUOUS,
        _expect_violation(
            "ambiguous retirement replacement owner fails",
            ("behavior_change_requires_complete_current_retirement_proof",),
        ),
    ),
    scenario(
        "retirement_orphaned_negative_case_fails",
        "Required negative cases and oracles must migrate before retirement.",
        BROKEN_RETIREMENT_NEGATIVE_CASE_ORPHANED,
        _expect_violation(
            "orphaned retirement negative case fails",
            ("behavior_change_requires_complete_current_retirement_proof",),
        ),
    ),
    scenario(
        "retirement_compatibility_survival_fails",
        "Retired behavior cannot remain alive behind another entrypoint.",
        BROKEN_RETIREMENT_COMPATIBILITY_SURVIVES,
        _expect_violation(
            "retirement compatibility survival fails",
            ("behavior_change_requires_complete_current_retirement_proof",),
        ),
    ),
    scenario(
        "missing_observable_contract_fails",
        "Code contraction needs an observable contract.",
        BROKEN_NO_OBSERVABLE_CONTRACT,
        _expect_violation("missing observable contract fails", ("observable_contract_exists",)),
    ),
    scenario(
        "missing_code_mapping_fails",
        "Model reductions must map back to code nodes.",
        BROKEN_NO_CODE_MAPPING,
        _expect_violation("missing code mapping fails", ("code_mapping_exists",)),
    ),
    scenario(
        "unclassified_candidates_fail",
        "Candidates must be classified.",
        BROKEN_UNCLASSIFIED_CANDIDATES,
        _expect_violation("unclassified candidates fail", ("candidates_and_proofs_are_visible",)),
    ),
    scenario(
        "hidden_proof_status_fails",
        "Proof status must stay visible.",
        BROKEN_HIDDEN_PROOF_STATUS,
        _expect_violation("hidden proof status fails", ("candidates_and_proofs_are_visible",)),
    ),
    scenario(
        "risky_candidates_hidden_fail",
        "Risky candidates must not be silently deleted.",
        BROKEN_RISKY_CANDIDATES_HIDDEN,
        _expect_violation("hidden risky candidates fail", ("risky_candidates_are_not_deleted_silently",)),
    ),
    scenario(
        "public_entrypoint_bypass_fails",
        "Public entrypoints need StructureMesh parity gates.",
        BROKEN_PUBLIC_ENTRYPOINT_BYPASS,
        _expect_violation("public entrypoint bypass fails", ("public_entrypoints_use_structuremesh_gate",)),
    ),
    scenario(
        "missing_target_handoff_fails",
        "Reduced model evidence must hand off target structure.",
        BROKEN_NO_TARGET_HANDOFF,
        _expect_violation("missing target structure handoff fails", ("target_structure_handoff_exists",)),
    ),
    scenario(
        "completed_candidate_requeued_fails",
        "Completed candidates must not remain ready work.",
        BROKEN_COMPLETED_CANDIDATE_REQUEUED,
        _expect_violation("completed candidate requeue fails", ("completed_candidates_leave_active_queue",)),
    ),
    scenario(
        "missing_companion_triggers_fails",
        "Related skills need architecture reduction triggers.",
        BROKEN_NO_COMPANION_TRIGGERS,
        _expect_violation("missing companion triggers fails", ("companion_route_triggers_exist",)),
    ),
    scenario(
        "direct_rewrite_fails",
        "Architecture reduction must not directly rewrite production code.",
        BROKEN_DIRECT_REWRITE,
        _expect_violation("direct rewrite fails", ("architecture_reduction_does_not_rewrite_code",)),
    ),
    scenario(
        "missing_validation_gates_fails",
        "Validation and parity gates must remain visible.",
        BROKEN_NO_VALIDATION_GATES,
        _expect_violation("missing validation gates fails", ("validation_gates_remain_visible",)),
    ),
    scenario(
        "missing_expected_candidate_inventory_fails",
        "Candidate completeness needs an independent expected inventory.",
        BROKEN_NO_EXPECTED_CANDIDATE_INVENTORY,
        _expect_violation("missing candidate inventory fails", ("expected_candidate_inventory_is_complete",)),
    ),
    scenario(
        "omitted_expected_candidate_fails",
        "Expected candidates must materialize or receive scoped disposition.",
        BROKEN_OMITTED_EXPECTED_CANDIDATE,
        _expect_violation("omitted expected candidate fails", ("expected_candidate_inventory_is_complete",)),
    ),
    scenario(
        "incomplete_signal_families_fail",
        "Every supported self-reduction signal family needs a terminal disposition.",
        BROKEN_INCOMPLETE_SIGNAL_FAMILIES,
        _expect_violation(
            "incomplete signal-family inventory fails",
            ("expected_candidate_inventory_is_complete",),
        ),
    ),
    scenario(
        "retained_route_internal_steps_omitted_fail",
        "Keeping a route does not hide repeated or expensive internal steps from the cleanup review.",
        BROKEN_INTERNAL_STEPS_OMITTED,
        _expect_violation(
            "omitted retained-route internal steps fail",
            ("retained_route_steps_use_evidence_bound_actions",),
        ),
    ),
    scenario(
        "non_current_step_action_vocabulary_fails",
        "Every internal step receives one direct-current action without aliases or fallback actions.",
        BROKEN_STEP_ACTION_VOCABULARY,
        _expect_violation(
            "non-current internal-step action vocabulary fails",
            ("retained_route_steps_use_evidence_bound_actions",),
        ),
    ),
    scenario(
        "stale_internal_step_cost_fails",
        "Operation and payload evidence must describe the current step inventory.",
        BROKEN_STEP_COST_STALE,
        _expect_violation(
            "stale internal-step cost evidence fails",
            ("retained_route_steps_use_evidence_bound_actions",),
        ),
    ),
    scenario(
        "high_cost_as_contraction_proof_fails",
        "Cost prioritizes review but never proves merge, delegation, removal, or on-demand behavior safe.",
        BROKEN_STEP_COST_AS_PROOF,
        _expect_violation(
            "high cost used as contraction proof fails",
            ("retained_route_steps_use_evidence_bound_actions",),
        ),
    ),
    scenario(
        "unique_safety_owner_removed_fails",
        "A costly step stays until its unique safety and evidence responsibilities have exact current owners.",
        BROKEN_UNIQUE_SAFETY_OWNER_REMOVED,
        _expect_violation(
            "unique safety owner removal fails",
            ("retained_route_steps_use_evidence_bound_actions",),
        ),
    ),
    scenario(
        "implicit_on_demand_trigger_fails",
        "Moving work behind an on-demand boundary requires an explicit trigger.",
        BROKEN_ON_DEMAND_TRIGGER_IMPLICIT,
        _expect_violation(
            "implicit on-demand trigger fails",
            ("retained_route_steps_use_evidence_bound_actions",),
        ),
    ),
    scenario(
        "label_only_self_blueprint_fails",
        "Self-reduction cannot accept a label-only or stale object as the current self-blueprint.",
        BROKEN_LABEL_ONLY_SELF_BLUEPRINT,
        _expect_violation(
            "label-only self-blueprint fails",
            ("self_reduction_claim_is_independently_evidence_bound",),
        ),
    ),
    scenario(
        "automatic_retain_disposition_fails",
        "A member without an independent terminal disposition must remain unresolved.",
        BROKEN_AUTOMATIC_RETAIN_DISPOSITION,
        _expect_violation(
            "automatic unresolved-to-retain rewrite fails",
            ("self_reduction_claim_is_independently_evidence_bound",),
        ),
    ),
    scenario(
        "candidate_signal_auto_retain_fails",
        "A signal that forms a contraction relation cannot be retained from source existence alone.",
        BROKEN_CANDIDATE_SIGNAL_AUTO_RETAIN,
        _expect_violation(
            "candidate signal auto-retain fails",
            ("self_reduction_claim_is_independently_evidence_bound",),
        ),
    ),
    scenario(
        "candidate_binding_cannot_self_prove_retain",
        "A candidate relation scopes comparison but cannot itself supply retain authority.",
        BROKEN_CANDIDATE_BINDING_SELF_PROVES_RETAIN,
        _expect_violation(
            "candidate binding self-proof fails",
            ("self_reduction_claim_is_independently_evidence_bound",),
        ),
    ),
    scenario(
        "same_commitment_auto_retain_fails",
        "Members with the same current behavior commitment remain unresolved until another typed proof closes the candidate.",
        BROKEN_SAME_COMMITMENT_AUTO_RETAIN,
        _expect_violation(
            "same commitment auto-retain fails",
            ("self_reduction_claim_is_independently_evidence_bound",),
        ),
    ),
    scenario(
        "retained_implementation_without_necessity_witness_fails",
        "Retained implementation requires one candidate-independent exact-current necessity witness.",
        BROKEN_RETAIN_WITHOUT_CURRENT_NECESSITY_WITNESS,
        _expect_violation(
            "retained implementation without a current necessity witness fails",
            ("retained_implementation_requires_semantic_necessity",),
        ),
    ),
    scenario(
        "mixed_test_and_model_validation_evidence_fails",
        "Ordinary test nodes and current model-regression evidence must be validated in separate namespaces before they jointly support one necessity witness.",
        BROKEN_MIXED_TEST_AND_MODEL_VALIDATION_EVIDENCE,
        _expect_violation(
            "mixed ordinary-test and model-validation evidence fails",
            ("retained_implementation_requires_semantic_necessity",),
        ),
    ),
    scenario(
        "identifier_only_semantic_difference_fails",
        "Structure and authority identifiers cannot manufacture a semantic difference.",
        BROKEN_IDENTIFIER_ONLY_SEMANTIC_DIFFERENCE,
        _expect_violation(
            "identifier-only semantic difference fails",
            ("retained_implementation_requires_semantic_necessity",),
        ),
    ),
    scenario(
        "external_promise_without_exact_owner_binding_fails",
        "An external promise must bind the exact current primary model, blueprint owner contract, and current test evidence.",
        BROKEN_EXTERNAL_PROMISE_WITHOUT_EXACT_OWNER_BINDING,
        _expect_violation(
            "external promise without exact model-code-test binding fails",
            ("retained_implementation_requires_semantic_necessity",),
        ),
    ),
    scenario(
        "public_role_without_current_promise_fails",
        "A public role alone does not establish one current product promise.",
        BROKEN_PUBLIC_ROLE_AS_CURRENT_PROMISE,
        _expect_violation(
            "public role without a current promise fails",
            ("public_role_is_not_a_current_promise",),
        ),
    ),
    scenario(
        "isolated_maintenance_name_candidate_fails",
        "An isolated maintenance-like lexical name remains only a signal.",
        BROKEN_ISOLATED_MAINTENANCE_NAME_CANDIDATE,
        _expect_violation(
            "isolated maintenance-name candidate materialization fails",
            ("maintenance_lexical_signal_requires_exact_relation",),
        ),
    ),
    scenario(
        "inexact_maintenance_relation_candidate_fails",
        "Maintenance candidate materialization requires one exact related multi-surface relation.",
        BROKEN_INEXACT_MAINTENANCE_RELATION_CANDIDATE,
        _expect_violation(
            "inexact maintenance relation candidate fails",
            ("maintenance_lexical_signal_requires_exact_relation",),
        ),
    ),
    scenario(
        "caller_forged_reduction_proof_fails",
        "A typed wrapper cannot replace independent verification of the current canonical receipt.",
        BROKEN_CALLER_FORGED_REDUCTION_PROOF,
        _expect_violation(
            "caller-forged reduction proof fails",
            ("self_reduction_claim_is_independently_evidence_bound",),
        ),
    ),
    scenario(
        "self_certified_leaf_proof_fails",
        "A caller-written passing leaf cannot replace supervised candidate test and parity child executions.",
        BROKEN_SELF_CERTIFIED_LEAF_PROOF,
        _expect_violation(
            "self-certified leaf proof fails",
            ("self_reduction_claim_is_independently_evidence_bound",),
        ),
    ),
    scenario(
        "exit_zero_candidate_test_fails",
        "A green process exit cannot replace exact collected-and-passed candidate nodes and executed oracle members.",
        BROKEN_EXIT_ZERO_CANDIDATE_TEST,
        _expect_violation(
            "exit-zero-only candidate test fails",
            ("self_reduction_claim_is_independently_evidence_bound",),
        ),
    ),
    scenario(
        "metadata_only_parity_fails",
        "Parity must execute the candidate-bound behavior and exact five-dimension oracles.",
        BROKEN_METADATA_ONLY_PARITY,
        _expect_violation(
            "metadata-only parity fails",
            ("self_reduction_claim_is_independently_evidence_bound",),
        ),
    ),
    scenario(
        "alternate_proof_store_fails",
        "A caller-selected temporary receipt root cannot become contraction authority.",
        BROKEN_ALTERNATE_PROOF_STORE,
        _expect_violation(
            "alternate proof store fails",
            ("self_reduction_claim_is_independently_evidence_bound",),
        ),
    ),
    scenario(
        "reparse_proof_store_fails",
        "Canonical evidence cannot traverse a symlink, junction, reparse point, or repository boundary.",
        BROKEN_REPARSE_PROOF_STORE,
        _expect_violation(
            "reparse proof store fails",
            ("self_reduction_claim_is_independently_evidence_bound",),
        ),
    ),
    scenario(
        "rewrapped_reduction_proof_fails",
        "Different candidates cannot reuse one proof artifact or result through distinct wrappers.",
        BROKEN_REWRAPPED_REDUCTION_PROOF,
        _expect_violation(
            "rewrapped reduction proof fails",
            ("self_reduction_claim_is_independently_evidence_bound",),
        ),
    ),
    scenario(
        "review_currentness_window_fails",
        "A cleanup review must recheck governed source and proof identities immediately before publication.",
        BROKEN_REVIEW_CURRENTNESS_WINDOW,
        _expect_violation(
            "review currentness window fails",
            ("self_reduction_claim_is_independently_evidence_bound",),
        ),
    ),
    scenario(
        "caller_authored_facade_fails",
        "Facade delegation facts must be derived from the current ledger and code binding.",
        BROKEN_CALLER_AUTHORED_FACADE,
        _expect_violation(
            "caller-authored facade facts fail",
            ("self_reduction_claim_is_independently_evidence_bound",),
        ),
    ),
    scenario(
        "ambiguous_short_caller_fails",
        "A short or receiver-qualified call without one exact target remains an explicit caller-resolution gap.",
        BROKEN_AMBIGUOUS_SHORT_CALLER,
        _expect_violation(
            "ambiguous short caller fails",
            ("self_reduction_claim_is_independently_evidence_bound",),
        ),
    ),
    scenario(
        "conflicting_member_actions_fail",
        "One code member cannot receive several contraction actions without one current primary candidate.",
        BROKEN_CONFLICTING_MEMBER_ACTIONS,
        _expect_violation(
            "conflicting member actions fail",
            ("self_reduction_claim_is_independently_evidence_bound",),
        ),
    ),
    scenario(
        "final_blueprint_not_rebuilt_fails",
        "Publication requires a fresh self-blueprint and denominator comparison after proof review.",
        BROKEN_FINAL_BLUEPRINT_NOT_REBUILT,
        _expect_violation(
            "missing final blueprint rebuild fails",
            ("self_reduction_claim_is_independently_evidence_bound",),
        ),
    ),
    scenario(
        "review_executes_proof_fails",
        "The review consumer is read-only; proof execution remains an explicit producer action.",
        BROKEN_REVIEW_EXECUTES_PROOF,
        _expect_violation(
            "review-side proof execution fails",
            ("self_reduction_claim_is_independently_evidence_bound",),
        ),
    ),
    scenario(
        "audit_noncanonical_aggregate_autodiscovery_fails",
        "Read-only audit auto-discovers only one exact-current canonical aggregate proof.",
        BROKEN_AUDIT_DISCOVERS_NONCANONICAL_AGGREGATE,
        _expect_violation(
            "noncanonical aggregate proof auto-discovery fails",
            ("read_only_audit_uses_one_current_aggregate_proof",),
        ),
    ),
    scenario(
        "implicit_unbounded_proof_batch_reuse_fails",
        "Proof production or reuse requires one explicit finite batch.",
        BROKEN_IMPLICIT_UNBOUNDED_PROOF_BATCH_REUSE,
        _expect_violation(
            "implicit or unbounded proof batch reuse fails",
            ("read_only_audit_uses_one_current_aggregate_proof",),
        ),
    ),
    scenario(
        "injected_proof_registry_fails",
        "Read-only audit cannot accept a caller-injected proof registry.",
        BROKEN_INJECTED_PROOF_REGISTRY,
        _expect_violation(
            "injected proof registry fails",
            ("read_only_audit_uses_one_current_aggregate_proof",),
        ),
    ),
    scenario(
        "stale_proof_history_selection_fails",
        "Stale historical proof is ignored instead of becoming current authority.",
        BROKEN_STALE_PROOF_HISTORY_SELECTED,
        _expect_violation(
            "stale proof history selection fails",
            ("read_only_audit_uses_one_current_aggregate_proof",),
        ),
    ),
    scenario(
        "duplicate_current_aggregate_proof_fails",
        "More than one exact-current aggregate proof blocks audit authority.",
        BROKEN_DUPLICATE_CURRENT_AGGREGATE_PROOF,
        _expect_violation(
            "duplicate current aggregate proof fails",
            ("read_only_audit_uses_one_current_aggregate_proof",),
        ),
    ),
    scenario(
        "opaque_canonical_relation_provenance_fails",
        "Canonical relation ids must bind concrete candidates and actions.",
        BROKEN_OPAQUE_CANONICAL_RELATION_PROVENANCE,
        _expect_violation(
            "opaque canonical relation provenance fails",
            ("canonical_relation_provenance_is_materialized",),
        ),
    ),
    scenario(
        "stale_facade_delegation_fails",
        "Facade delegation evidence must be current.",
        BROKEN_STALE_FACADE_DELEGATION,
        _expect_violation("stale facade delegation fails", ("retained_facades_delegate_only",)),
    ),
    scenario(
        "facade_parallel_success_fails",
        "Facade cannot own an independent business success.",
        BROKEN_FACADE_PARALLEL_SUCCESS,
        _expect_violation("facade parallel success fails", ("retained_facades_delegate_only",)),
    ),
    scenario(
        "repeated_caller_scan_fails",
        "Candidate caller discovery must not rescan all surfaces per member.",
        BROKEN_REPEATED_CALLER_SCAN,
        _expect_violation(
            "repeated caller scan fails",
            ("self_reduction_execution_is_single_pass",),
        ),
    ),
    scenario(
        "duplicate_self_blueprint_build_fails",
        "Composed self-maintenance must reuse one exact in-memory blueprint.",
        BROKEN_DUPLICATE_SELF_BLUEPRINT_BUILD,
        _expect_violation(
            "duplicate self-blueprint build fails",
            ("self_reduction_execution_is_single_pass",),
        ),
    ),
    scenario(
        "compact_full_expansion_fails",
        "Compact self-maintenance must not expand the complete blueprint before emitting its bounded projection.",
        BROKEN_COMPACT_FULL_EXPANSION,
        _expect_violation(
            "compact full expansion fails",
            ("self_reduction_execution_is_single_pass",),
        ),
    ),
    scenario(
        "repeated_large_report_fingerprint_fails",
        "Immutable large behavior evidence must not rebuild its complete fingerprint payload for each consumer.",
        BROKEN_REPEATED_LARGE_REPORT_FINGERPRINT,
        _expect_violation(
            "repeated large-report fingerprint fails",
            ("self_reduction_execution_is_single_pass",),
        ),
    ),
    scenario(
        "materialized_large_payload_fingerprint_fails",
        "Large canonical blueprint payloads must not retain several complete serialized copies while computing size and fingerprint.",
        BROKEN_MATERIALIZED_LARGE_PAYLOAD_FINGERPRINT,
        _expect_violation(
            "materialized large-payload fingerprint fails",
            ("self_reduction_execution_is_single_pass",),
        ),
    ),
    scenario(
        "cartesian_candidate_evidence_fails",
        "Shared candidate test evidence must be stored once rather than expanded across every candidate.",
        BROKEN_CARTESIAN_CANDIDATE_EVIDENCE,
        _expect_violation(
            "cartesian candidate evidence fails",
            ("self_reduction_execution_is_single_pass",),
        ),
    ),
    scenario(
        "unbounded_comparison_candidate_batch_fails",
        "Comparison and unreferenced-helper cleanup candidates must use deterministic finite member batches rather than one unbounded relation or module group.",
        BROKEN_UNBOUNDED_COMPARISON_CANDIDATE_BATCH,
        _expect_violation(
            "unbounded comparison-candidate batch fails",
            ("self_reduction_execution_is_single_pass",),
        ),
    ),
    scenario(
        "candidate_evidence_reference_gap_fails",
        "A candidate evidence reference must resolve one exact current catalog row without an inline fallback.",
        BROKEN_CANDIDATE_EVIDENCE_REFERENCE,
        _expect_violation(
            "candidate evidence reference gap fails",
            ("self_reduction_execution_is_single_pass",),
        ),
    ),
    scenario(
        "repeated_affected_object_denominator_fails",
        "Affected and topology edges must reuse one exact validated object-id denominator.",
        BROKEN_REPEATED_AFFECTED_OBJECT_DENOMINATOR,
        _expect_violation(
            "repeated affected-object denominator fails",
            ("self_reduction_execution_is_single_pass",),
        ),
    ),
    scenario(
        "proofless_audit_status_conflation_fails",
        "A complete audit may pass while proofless candidates remain visible as unresolved risky keep and cleanup remains not ready.",
        BROKEN_PROOFLESS_AUDIT_STATUS_CONFLATION,
        _expect_violation(
            "proofless audit and cleanup readiness conflation fails",
            ("audit_completion_is_distinct_from_cleanup_authorization",),
        ),
    ),
    scenario(
        "safe_unapplied_audit_pass_fails",
        "A proof-authorized candidate that has not been applied still blocks the release audit.",
        BROKEN_SAFE_UNAPPLIED_AUDIT_PASS,
        _expect_violation(
            "safe unapplied candidate cannot pass the release audit",
            ("audit_completion_is_distinct_from_cleanup_authorization",),
        ),
    ),
    scenario(
        "cleanup_ready_with_unresolved_candidate_fails",
        "Cleanup readiness requires every candidate to be resolved and every authorized action to be applied.",
        BROKEN_CLEANUP_READY_WITH_UNRESOLVED,
        _expect_violation(
            "cleanup readiness with unresolved candidates fails",
            ("audit_completion_is_distinct_from_cleanup_authorization",),
        ),
    ),
    scenario(
        "cleanup_ready_with_unresolved_step_fails",
        "A complete ordinary audit cannot claim cleanup closure while an internal candidate step remains unresolved.",
        BROKEN_CLEANUP_READY_WITH_UNRESOLVED_STEP,
        _expect_violation(
            "cleanup readiness with unresolved step fails",
            ("audit_completion_is_distinct_from_cleanup_authorization",),
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
    """Project the existing architecture-reduction owner for SkillGuard V2."""

    return build_skill_contract_model_export(
        skill_id="flowguard-architecture-reduction",
        route_id="architecture_reduction",
        owner_id="architecture_reduction",
        parent_model_id="flowguard.model_first_function_flow",
        business_intent="Reduce mapped architecture through observable equivalence, or deliberately retire obsolete behavior through one complete current responsibility proof, without creating a second authority.",
        claim_boundary="Projection only; native equivalence and retirement scenarios, proof status, responsibility dispositions, and downstream parity evidence remain authoritative.",
    )
