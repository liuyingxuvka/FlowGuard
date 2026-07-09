"""Run FlowGuard checks for the self-maintenance mesh."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flowguard import (
    SELF_MAINTENANCE_STATUS_PASS,
    SelfMaintenanceChildReport,
    default_flowguard_self_maintenance_plan,
    review_flowguard_self_maintenance,
)
from flowguard.formal_runner import FormalWorkflowCase, run_formal_workflow_suite
import model


REQUIRED_LABELS = (
    "route_graph_connected",
    "field_layers_declared",
    "focused_validation_passed",
    "local_surfaces_synced",
    "done_accepted",
)


def run_workflow_suite() -> bool:
    report = run_formal_workflow_suite(
        "self_maintenance_mesh",
        (
            FormalWorkflowCase("correct_self_maintenance", model.build_correct_workflow(), True),
            FormalWorkflowCase("broken_route_graph_only", model.build_broken_route_graph_only_workflow(), False),
            FormalWorkflowCase(
                "broken_missing_behavior_ledger",
                model.build_broken_missing_behavior_ledger_workflow(),
                False,
            ),
            FormalWorkflowCase(
                "broken_missing_dcar_coverage",
                model.build_broken_missing_dcar_coverage_workflow(),
                False,
            ),
            FormalWorkflowCase(
                "broken_missing_test_mesh_shards",
                model.build_broken_missing_test_mesh_shards_workflow(),
                False,
            ),
            FormalWorkflowCase(
                "broken_missing_model_miss_backfeed",
                model.build_broken_missing_model_miss_backfeed_workflow(),
                False,
            ),
            FormalWorkflowCase("broken_missing_sync", model.build_broken_missing_sync_workflow(), False),
        ),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        required_labels=REQUIRED_LABELS,
        protected_error_class="self_maintenance_incomplete",
    )
    return report.ok


def run_route_profile_review() -> bool:
    def child_report(child_id: str, owner_guard: str, artifact_kind: str, safe_claim: str) -> SelfMaintenanceChildReport:
        return SelfMaintenanceChildReport(
            child_id,
            owner_guard,
            artifact_kind,
            closure_status=SELF_MAINTENANCE_STATUS_PASS,
            current=True,
            safe_claim=safe_claim,
            unsafe_claim_boundary="does not prove final release confidence without package, shadow, and git sync",
        )

    report = review_flowguard_self_maintenance(
        default_flowguard_self_maintenance_plan(
            "self-maintenance-route-profile-review",
            child_reports=(
                child_report(
                    "route-graph",
                    "flowguard_self_maintenance",
                    "route_graph",
                    "route profiles are discoverable through FLOWGUARD_ROUTE_API",
                ),
                child_report(
                    "behavior-commitment-ledger",
                    "behavior_commitment_ledger",
                    "behavior_commitment_ledger",
                    "self-maintenance behavior commitments are checked before broad claims",
                ),
                child_report(
                    "contract-exhaustion-mesh",
                    "contract_exhaustion_mesh",
                    "contract_exhaustion_mesh",
                    "self-maintenance DCAR axes and groups are checked before broad claims",
                ),
                child_report(
                    "test-mesh",
                    "test_mesh_maintenance",
                    "test_mesh_maintenance",
                    "self-maintenance test shards are current before broad claims",
                ),
                child_report(
                    "model-miss-backfeed",
                    "model_miss_review",
                    "model_miss_review",
                    "model-miss failures feed back into existing commitments before broad claims",
                ),
            ),
        )
    )
    print(report.format_text())
    print()
    return report.ok and not report.findings


def main() -> int:
    checks = (
        run_workflow_suite(),
        run_route_profile_review(),
    )
    if all(checks):
        print("self_maintenance_mesh checks passed")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
