"""Run FlowGuard checks for the self-maintenance mesh."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flowguard import (
    FLOWGUARD_ROUTE_API,
    default_flowguard_self_maintenance_plan,
    default_flowguard_route_profiles,
    review_flowguard_self_maintenance,
    review_route_admission,
    validate_default_route_topology,
)
from flowguard.formal_runner import FormalWorkflowCase, run_exact_workflow_case, run_formal_workflow_suite
from flowguard.skill_self_governance import load_verification_contexts, run_skill_self_governance
import model


REQUIRED_LABELS = (
    "route_graph_connected",
    "field_layers_declared",
    "receipt_set_consumed",
    "focused_validation_passed",
    "local_surfaces_synced",
    "done_accepted",
)


def semantic_receipt_action(
    verification: model.SemanticMeshVerification,
) -> model.SelfMaintenanceAction:
    return model.SelfMaintenanceAction(
        "consume_verified_receipt_set",
        verified_child_receipt_ids=model.REQUIRED_SKILL_RECEIPT_IDS,
        verification_set_fingerprint="sha256:current-skill-set",
        verified_plane_upgrade_receipt_ids=model.CURRENT_FULL_VALIDATION_OWNER_IDS,
        terminal_plane_upgrade_receipt_ids=model.CURRENT_FULL_VALIDATION_OWNER_IDS,
        validation_owner_inventory_fingerprint=(
            model.VALIDATION_OWNER_INVENTORY_FINGERPRINT
        ),
        verified_understanding_artifact_ids=(
            model.REQUIRED_UNDERSTANDING_ARTIFACT_IDS
        ),
        understanding_chain_fingerprint=(
            model.semantic_understanding_chain_fingerprint(
                model.REQUIRED_UNDERSTANDING_ARTIFACT_IDS,
                verification,
            )
        ),
        semantic_mesh_verification=verification,
        spec_context_ids=model.REQUIRED_SPEC_CONTEXT_IDS,
        spec_context_provider="openspec",
        spec_context_artifacts_current=True,
        spec_context_read_only=True,
        spec_receipt_bridge_present=False,
    )


def semantic_mesh_bad_cases() -> tuple[tuple[str, model.SelfMaintenanceAction], ...]:
    current = model.ABSTRACT_SEMANTIC_MESH_VERIFICATION
    assert current.terminal_proof is not None

    foreign_fingerprint = replace(
        current,
        terminal_proof=replace(
            current.terminal_proof,
            subject_fingerprint=(
                "sha256:" + hashlib.sha256(b"foreign-semantic-mesh").hexdigest()
            ),
        ),
    )
    forged_terminal = replace(
        current,
        terminal_proof=replace(
            current.terminal_proof,
            command="",
            result_path="",
            started_at="",
            finished_at="",
            result_status="passed",
            exit_code=0,
        ),
    )
    previous_revision = (
        "sha256:" + hashlib.sha256(b"previous-model-revision").hexdigest()
    )
    previous_revision_evidence = replace(
        current,
        semantic_mesh_revision=previous_revision,
        verified_subject_revision=previous_revision,
        terminal_proof=replace(
            current.terminal_proof,
            subject_id=f"semantic-mesh:{previous_revision}",
        ),
    )
    return (
        ("foreign_semantic_mesh_fingerprint", semantic_receipt_action(foreign_fingerprint)),
        ("forged_terminal_semantic_mesh_proof", semantic_receipt_action(forged_terminal)),
        ("previous_semantic_mesh_revision", semantic_receipt_action(previous_revision_evidence)),
    )


def run_workflow_suite(*, typed_topology_ok: bool) -> bool:
    correct_ok = run_exact_workflow_case(
        "receipt-bound correct model",
        workflow=model.build_correct_workflow(),
        initial_state=model.initial_state(),
        external_input_sequence=model.EXTERNAL_INPUTS * model.MAX_SEQUENCE_LENGTH,
        invariants=model.INVARIANTS,
        final_state_predicate=lambda state: state.done_claim == "accepted",
    )
    report = run_formal_workflow_suite(
        "self_maintenance_mesh",
        (
            FormalWorkflowCase(
                "broken_synthetic_all_flags",
                model.build_broken_synthetic_all_flags_workflow(),
                False,
                required_labels=("synthetic_all_flags",),
                external_inputs=(model.SelfMaintenanceAction("declare_field_layers"),),
                max_sequence_length=1,
            ),
            FormalWorkflowCase(
                "broken_unrelated_receipt_substitution",
                model.build_broken_unverified_plane_receipts_workflow(),
                False,
                required_labels=("unverified_receipts_consumed",),
                external_inputs=(
                    model.SelfMaintenanceAction(
                        "consume_verified_receipt_set",
                        verified_child_receipt_ids=model.REQUIRED_SKILL_RECEIPT_IDS,
                        verification_set_fingerprint="sha256:current-skill-set",
                        verified_plane_upgrade_receipt_ids=tuple(
                            f"unrelated-check-{index:02d}"
                            for index in range(len(model.CURRENT_FULL_VALIDATION_OWNER_IDS))
                        ),
                        terminal_plane_upgrade_receipt_ids=tuple(
                            f"unrelated-check-{index:02d}"
                            for index in range(len(model.CURRENT_FULL_VALIDATION_OWNER_IDS))
                        ),
                        validation_owner_inventory_fingerprint=(
                            model.VALIDATION_OWNER_INVENTORY_FINGERPRINT
                        ),
                    ),
                ),
                max_sequence_length=1,
            ),
            FormalWorkflowCase(
                "broken_progress_only_full_test_receipt",
                model.build_broken_unverified_plane_receipts_workflow(),
                False,
                required_labels=("unverified_receipts_consumed",),
                external_inputs=(
                    model.SelfMaintenanceAction(
                        "consume_verified_receipt_set",
                        verified_child_receipt_ids=model.REQUIRED_SKILL_RECEIPT_IDS,
                        verification_set_fingerprint="sha256:current-skill-set",
                        verified_plane_upgrade_receipt_ids=model.CURRENT_FULL_VALIDATION_OWNER_IDS,
                        terminal_plane_upgrade_receipt_ids=tuple(
                            check_id
                            for check_id in model.CURRENT_FULL_VALIDATION_OWNER_IDS
                            if check_id != "pytest"
                        ),
                        progress_only_plane_upgrade_receipt_ids=("pytest",),
                        validation_owner_inventory_fingerprint=(
                            model.VALIDATION_OWNER_INVENTORY_FINGERPRINT
                        ),
                    ),
                ),
                max_sequence_length=1,
            ),
            FormalWorkflowCase(
                "broken_v2_parity_receipt_replaced",
                model.build_broken_unverified_plane_receipts_workflow(),
                False,
                required_labels=("unverified_receipts_consumed",),
                external_inputs=(
                    model.SelfMaintenanceAction(
                        "consume_verified_receipt_set",
                        verified_child_receipt_ids=model.REQUIRED_SKILL_RECEIPT_IDS,
                        verification_set_fingerprint="sha256:current-skill-set",
                        verified_plane_upgrade_receipt_ids=tuple(
                            "distribution_declaration_only"
                            if check_id == "distribution_check"
                            else check_id
                            for check_id in model.CURRENT_FULL_VALIDATION_OWNER_IDS
                        ),
                        terminal_plane_upgrade_receipt_ids=tuple(
                            "distribution_declaration_only"
                            if check_id == "distribution_check"
                            else check_id
                            for check_id in model.CURRENT_FULL_VALIDATION_OWNER_IDS
                        ),
                        validation_owner_inventory_fingerprint=(
                            model.VALIDATION_OWNER_INVENTORY_FINGERPRINT
                        ),
                    ),
                ),
                max_sequence_length=1,
            ),
            FormalWorkflowCase(
                "broken_route_graph_only",
                model.build_broken_route_graph_only_workflow(),
                False,
                required_labels=("route_graph_connected", "done_accepted"),
                external_inputs=(
                    model.SelfMaintenanceAction("connect_route_graph"),
                    model.SelfMaintenanceAction("claim_done"),
                ),
                max_sequence_length=2,
            ),
            FormalWorkflowCase(
                "broken_missing_behavior_ledger",
                model.build_broken_missing_behavior_ledger_workflow(),
                False,
                required_labels=("field_layers_declared",),
                external_inputs=(model.SelfMaintenanceAction("declare_field_layers"),),
                max_sequence_length=1,
            ),
            FormalWorkflowCase(
                "broken_missing_dcar_coverage",
                model.build_broken_missing_dcar_coverage_workflow(),
                False,
                required_labels=("field_layers_declared",),
                external_inputs=(model.SelfMaintenanceAction("declare_field_layers"),),
                max_sequence_length=1,
            ),
            FormalWorkflowCase(
                "broken_missing_test_mesh_shards",
                model.build_broken_missing_test_mesh_shards_workflow(),
                False,
                required_labels=("field_layers_declared",),
                external_inputs=(model.SelfMaintenanceAction("declare_field_layers"),),
                max_sequence_length=1,
            ),
            FormalWorkflowCase(
                "broken_missing_model_miss_backfeed",
                model.build_broken_missing_model_miss_backfeed_workflow(),
                False,
                required_labels=("field_layers_declared",),
                external_inputs=(model.SelfMaintenanceAction("declare_field_layers"),),
                max_sequence_length=1,
            ),
            FormalWorkflowCase(
                "broken_missing_plane_upgrade_reports",
                model.build_broken_missing_plane_upgrade_reports_workflow(),
                False,
                required_labels=("field_layers_declared",),
                external_inputs=(model.SelfMaintenanceAction("declare_field_layers"),),
                max_sequence_length=1,
            ),
            FormalWorkflowCase(
                "broken_missing_understanding_chain",
                model.build_broken_missing_understanding_chain_workflow(),
                False,
                required_labels=("field_layers_declared",),
                external_inputs=(model.SelfMaintenanceAction("declare_field_layers"),),
                max_sequence_length=1,
            ),
            *(
                FormalWorkflowCase(
                    f"broken_{case_id}",
                    model.build_broken_unverified_plane_receipts_workflow(),
                    False,
                    required_labels=("unverified_receipts_consumed",),
                    external_inputs=(action,),
                    max_sequence_length=1,
                )
                for case_id, action in semantic_mesh_bad_cases()
            ),
            FormalWorkflowCase(
                "broken_wrong_plane_completion_authority",
                model.build_broken_wrong_plane_completion_workflow(),
                False,
                required_labels=("wrong_plane_done_accepted",),
                external_inputs=(
                    model.SelfMaintenanceAction(
                        "claim_done",
                        behavior_plane="agent_operation",
                    ),
                ),
                max_sequence_length=1,
            ),
            FormalWorkflowCase(
                "broken_missing_sync",
                model.build_broken_missing_sync_workflow(),
                False,
                required_labels=("done_accepted",),
                external_inputs=(
                    model.SelfMaintenanceAction("connect_route_graph"),
                    model.SelfMaintenanceAction("declare_field_layers"),
                    model.SelfMaintenanceAction(
                        "consume_verified_receipt_set",
                        verified_child_receipt_ids=model.ABSTRACT_RECEIPT_IDS,
                        verification_set_fingerprint="sha256:abstract-current-receipt-set",
                        verified_plane_upgrade_receipt_ids=model.CURRENT_FULL_VALIDATION_OWNER_IDS,
                        terminal_plane_upgrade_receipt_ids=model.CURRENT_FULL_VALIDATION_OWNER_IDS,
                        validation_owner_inventory_fingerprint=(
                            model.VALIDATION_OWNER_INVENTORY_FINGERPRINT
                        ),
                    ),
                    model.SelfMaintenanceAction("run_focused_validation"),
                    model.SelfMaintenanceAction("claim_done"),
                ),
                max_sequence_length=5,
            ),
            FormalWorkflowCase(
                "broken_missing_spec_context_close",
                model.build_broken_missing_spec_context_workflow(),
                False,
                required_labels=("done_accepted",),
                external_inputs=(
                    model.SelfMaintenanceAction("connect_route_graph"),
                    model.SelfMaintenanceAction("declare_field_layers"),
                    model.SelfMaintenanceAction(
                        "consume_verified_receipt_set",
                        verified_child_receipt_ids=model.ABSTRACT_RECEIPT_IDS,
                        verification_set_fingerprint="sha256:abstract-current-receipt-set",
                        verified_plane_upgrade_receipt_ids=model.CURRENT_FULL_VALIDATION_OWNER_IDS,
                        terminal_plane_upgrade_receipt_ids=model.CURRENT_FULL_VALIDATION_OWNER_IDS,
                        validation_owner_inventory_fingerprint=model.VALIDATION_OWNER_INVENTORY_FINGERPRINT,
                    ),
                    model.SelfMaintenanceAction("run_focused_validation"),
                    model.SelfMaintenanceAction("sync_local_surfaces"),
                    model.SelfMaintenanceAction("claim_done"),
                ),
                max_sequence_length=6,
            ),
        ),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        required_labels=REQUIRED_LABELS,
        protected_error_class="self_maintenance_incomplete",
    )
    return correct_ok and report.ok and typed_topology_ok


def run_semantic_mesh_verification_review() -> bool:
    block = model.CorrectSelfMaintenance()
    good_result = tuple(
        block.apply(
            semantic_receipt_action(model.ABSTRACT_SEMANTIC_MESH_VERIFICATION),
            model.initial_state(),
        )
    )
    good_ok = (
        len(good_result) == 1
        and good_result[0].output.status == "receipt_set_consumed"
        and good_result[0].new_state.understanding_chain_current
        and good_result[0].new_state.semantic_model_mesh_current
    )
    bad_results: list[str] = []
    for case_id, action in semantic_mesh_bad_cases():
        results = tuple(block.apply(action, model.initial_state()))
        rejected = (
            len(results) == 1
            and results[0].output.status == "receipt_set_rejected"
            and not results[0].new_state.understanding_chain_current
            and not results[0].new_state.semantic_model_mesh_current
        )
        if not rejected:
            bad_results.append(case_id)
    ok = good_ok and not bad_results
    print(
        "exact semantic-mesh verification binding: "
        f"{'pass' if ok else 'fail'}; "
        f"models={len(model.ABSTRACT_SEMANTIC_MESH_VERIFICATION.semantic_model_ids)}; "
        f"relations={len(model.ABSTRACT_SEMANTIC_MESH_VERIFICATION.semantic_relation_ids)}; "
        f"bad_cases={len(semantic_mesh_bad_cases())}; "
        f"unexpected={','.join(bad_results) or 'none'}"
    )
    print()
    return ok


def run_route_profile_review() -> bool:
    report = review_flowguard_self_maintenance(
        default_flowguard_self_maintenance_plan(
            "self-maintenance-route-profile-review",
            child_reports=(),
            broad_claim=False,
        )
    )
    print(report.format_text())
    print()
    return report.ok and not report.findings


def run_narrow_route_admission_review() -> bool:
    profiles = default_flowguard_route_profiles()
    public_profiles = tuple(
        profile for profile in profiles if profile.route_id in FLOWGUARD_ROUTE_API
    )
    complete = all(
        profile.positive_condition_ids
        and profile.forbidden_condition_ids
        and profile.first_action
        and profile.reference_edges
        and profile.deepening_trigger_ids
        and profile.claim_boundary
        for profile in public_profiles
    )
    selected = review_route_admission(profiles, ("behavior_preserving_contraction",))
    forbidden = review_route_admission(
        profiles,
        ("behavior_preserving_contraction", "behavior_change"),
    )
    conflict = review_route_admission(
        profiles,
        ("field_lifecycle_change", "finite_bad_case_universe"),
    )
    ok = (
        {profile.route_id for profile in public_profiles} == set(FLOWGUARD_ROUTE_API)
        and complete
        and selected.selected_route_id == "architecture_reduction"
        and forbidden.status == "no_match"
        and conflict.status == "conflict"
    )
    print(
        "narrow public route admission profiles: "
        f"{'pass' if ok else 'fail'}; public_routes={len(public_profiles)}"
    )
    print()
    return ok


def run_receipt_parent_review() -> bool:
    context_path = ROOT / ".flowguard/evidence/skill-suite-contexts.json"
    contexts = load_verification_contexts(context_path) if context_path.exists() else {}
    report = run_skill_self_governance(
        ROOT,
        verification_contexts=contexts,
        save_parent_receipt=True,
    )
    print(report.format_text())
    print()
    if report.ok:
        parent = report.self_governance_receipt
        return bool(
            parent
            and len(parent.required_child_receipts) == model.REQUIRED_RECEIPT_COUNT
            and len(parent.consumed_child_receipts) == model.REQUIRED_RECEIPT_COUNT
            and report.self_governance_receipt_hash == parent.fingerprint
        )
    # Environment-local evidence is intentionally not committed. A model
    # regression still succeeds only if absence/staleness is rejected without
    # manufacturing a parent green receipt.
    return bool(report.blockers and report.self_governance_receipt is None)


def run_route_topology_review() -> bool:
    report = validate_default_route_topology(ROOT)
    print(report.format_text())
    print()
    expected_cycles = {
        frozenset(
            {
                "development_process_flow",
                "flowguard_closure_contract",
                "maintenance_scan_router",
                "model_test_alignment",
                "risk_evidence_ledger",
                "structure_mesh_maintenance",
                "test_mesh_maintenance",
            }
        ),
        frozenset({"existing_model_preflight", "model_similarity_consolidation"}),
    }
    observed_cycles = {frozenset(component) for component in report.cycle_components}
    return (
        report.ok
        and report.edge_count > 0
        and observed_cycles == expected_cycles
        and all(probe.decision in {"continue", "blocked_unchanged_progress"} for probe in report.cycle_probes)
    )


def run_plane_upgrade_contract_binding() -> bool:
    check_ids = model.CURRENT_FULL_VALIDATION_OWNER_IDS
    actual_fingerprint = (
        "sha256:"
        + hashlib.sha256("\n".join(check_ids).encode("utf-8")).hexdigest().upper()
    )
    ok = (
        actual_fingerprint == model.VALIDATION_OWNER_INVENTORY_FINGERPRINT
        and len(check_ids) == len(set(check_ids))
        and "spec-check-run" not in check_ids
        and "spec-session-begin" not in check_ids
    )
    print(
        "current full-validation owner inventory binding: "
        f"{'pass' if ok else 'fail'}; checks={len(check_ids)}; fingerprint={actual_fingerprint}"
    )
    print()
    return ok


def main() -> int:
    typed_topology_ok = run_route_topology_review()
    plane_upgrade_contract_ok = run_plane_upgrade_contract_binding()
    semantic_mesh_verification_ok = run_semantic_mesh_verification_review()
    checks = (
        run_workflow_suite(
            typed_topology_ok=(
                typed_topology_ok
                and plane_upgrade_contract_ok
                and semantic_mesh_verification_ok
            )
        ),
        run_route_profile_review(),
        run_narrow_route_admission_review(),
        run_receipt_parent_review(),
        typed_topology_ok,
        plane_upgrade_contract_ok,
        semantic_mesh_verification_ok,
    )
    if all(checks):
        print("self_maintenance_mesh checks passed")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
