"""Run FlowGuard checks for the self-maintenance mesh."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flowguard import (
    default_flowguard_self_maintenance_plan,
    review_flowguard_self_maintenance,
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
                    ),
                    model.SelfMaintenanceAction("run_focused_validation"),
                    model.SelfMaintenanceAction("claim_done"),
                ),
                max_sequence_length=5,
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
            and len(parent.required_child_receipts) == 17
            and len(parent.consumed_child_receipts) == 17
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


def main() -> int:
    typed_topology_ok = run_route_topology_review()
    checks = (
        run_workflow_suite(typed_topology_ok=typed_topology_ok),
        run_route_profile_review(),
        run_receipt_parent_review(),
        typed_topology_ok,
    )
    if all(checks):
        print("self_maintenance_mesh checks passed")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
