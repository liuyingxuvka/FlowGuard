"""Run FlowGuard checks for the self-maintenance mesh."""

from __future__ import annotations

from flowguard import (
    Explorer,
    SELF_MAINTENANCE_STATUS_PASS,
    SelfMaintenanceChildReport,
    SelfMaintenancePlan,
    default_ai_maintenance_profiles,
    default_field_layer_profiles,
    default_flowguard_route_profiles,
    review_flowguard_self_maintenance,
)
import flowguard
import model


def run_workflow(name: str, workflow, *, expect_ok: bool) -> bool:
    report = Explorer(
        workflow=workflow,
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        required_labels=(
            "route_graph_connected",
            "field_layers_declared",
            "focused_validation_passed",
            "local_surfaces_synced",
            "done_accepted",
        ),
    ).explore()
    ok = report.ok
    print(f"{name}: {'OK' if ok else 'VIOLATION'}")
    print(report.format_text(max_examples=1))
    print()
    return ok is expect_ok


def run_route_profile_review() -> bool:
    report = review_flowguard_self_maintenance(
        SelfMaintenancePlan(
            "self-maintenance-route-profile-review",
            route_profiles=default_flowguard_route_profiles(),
            api_route_group_ids=tuple(flowguard.FLOWGUARD_ROUTE_API),
            ai_profiles=default_ai_maintenance_profiles(),
            field_layers=default_field_layer_profiles(),
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
        run_workflow("correct_self_maintenance", model.build_correct_workflow(), expect_ok=True),
        run_workflow(
            "broken_route_graph_only",
            model.build_broken_route_graph_only_workflow(),
            expect_ok=False,
        ),
        run_workflow(
            "broken_missing_sync",
            model.build_broken_missing_sync_workflow(),
            expect_ok=False,
        ),
        run_route_profile_review(),
    )
    if all(checks):
        print("self_maintenance_mesh checks passed")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
