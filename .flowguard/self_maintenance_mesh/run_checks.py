"""Run FlowGuard checks for the self-maintenance mesh."""

from __future__ import annotations

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
    report = review_flowguard_self_maintenance(
        default_flowguard_self_maintenance_plan(
            "self-maintenance-route-profile-review",
            child_reports=(
                SelfMaintenanceChildReport(
                    "route-graph",
                    "flowguard_self_maintenance",
                    "route_graph",
                    closure_status=SELF_MAINTENANCE_STATUS_PASS,
                    current=True,
                    safe_claim="route profiles are discoverable through FLOWGUARD_ROUTE_API",
                    unsafe_claim_boundary="does not prove route internals or final release confidence",
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
