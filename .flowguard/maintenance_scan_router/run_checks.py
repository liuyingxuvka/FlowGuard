"""Run FlowGuard checks for the maintenance scan router."""

from __future__ import annotations

from flowguard import (
    MAINTENANCE_ARTIFACT_CODE,
    MAINTENANCE_ARTIFACT_MODEL,
    MAINTENANCE_ROUTE_AGENT_WORKFLOW_REHEARSAL,
    MAINTENANCE_ROUTE_MODEL_TEST_ALIGNMENT,
    MAINTENANCE_ROUTE_STRUCTURE_MESH,
    MAINTENANCE_SCAN_DECISION_REQUIRED,
    MAINTENANCE_SCAN_DECISION_SCOPED,
    MAINTENANCE_SIGNAL_LARGE_MODULE,
    MaintenanceChangedArtifact,
    MaintenanceScanPlan,
    MaintenanceSignal,
    MaintenanceSkippedRoute,
    review_maintenance_scan,
)
from flowguard.formal_runner import FormalWorkflowCase, run_formal_workflow_suite
import model


REQUIRED_LABELS = (
    "model_test_alignment_routed",
    "structure_mesh_routed",
    "agent_workflow_rehearsal_routed",
    "owner_evidence_recorded",
    "full_claim_accepted",
)


def run_workflow_suite() -> bool:
    cases = [FormalWorkflowCase("correct_maintenance_scan_router", model.build_correct_workflow(), True)]
    cases.extend(FormalWorkflowCase(broken.name, broken, False) for broken in model.build_broken_workflows())
    report = run_formal_workflow_suite(
        "maintenance_scan_router",
        tuple(cases),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        required_labels=REQUIRED_LABELS,
        protected_error_class="maintenance_scan_route_missing",
    )
    return report.ok


def helper_case(name: str, plan: MaintenanceScanPlan, expected_decision: str, expected_routes: tuple[str, ...]) -> bool:
    report = review_maintenance_scan(plan)
    routes = {action.route_id for action in report.actions}
    ok = report.decision == expected_decision and set(expected_routes).issubset(routes)
    print(f"{name}: {'OK' if ok else 'VIOLATION'}")
    print(report.format_text())
    print()
    return ok


def run_helper_cases() -> bool:
    return all(
        (
            helper_case(
                "model_code_test_routes_alignment",
                MaintenanceScanPlan(
                    "self-model-alignment",
                    claim_scope="done",
                    changed_artifacts=(
                        MaintenanceChangedArtifact("model", MAINTENANCE_ARTIFACT_MODEL),
                        MaintenanceChangedArtifact("code", MAINTENANCE_ARTIFACT_CODE),
                    ),
                ),
                MAINTENANCE_SCAN_DECISION_SCOPED,
                (MAINTENANCE_ROUTE_MODEL_TEST_ALIGNMENT,),
            ),
            helper_case(
                "large_module_routes_structure_mesh",
                MaintenanceScanPlan(
                    "self-model-structure",
                    signals=(MaintenanceSignal("large-module", MAINTENANCE_SIGNAL_LARGE_MODULE),),
                ),
                MAINTENANCE_SCAN_DECISION_REQUIRED,
                (MAINTENANCE_ROUTE_STRUCTURE_MESH,),
            ),
            helper_case(
                "unaccepted_skip_routes_rehearsal",
                MaintenanceScanPlan(
                    "self-model-skipped",
                    skipped_routes=(MaintenanceSkippedRoute(MAINTENANCE_ROUTE_STRUCTURE_MESH),),
                ),
                MAINTENANCE_SCAN_DECISION_REQUIRED,
                (MAINTENANCE_ROUTE_AGENT_WORKFLOW_REHEARSAL,),
            ),
        )
    )


def main() -> int:
    workflow_checks = run_workflow_suite()
    helper_checks = run_helper_cases()
    return 0 if workflow_checks and helper_checks else 1


if __name__ == "__main__":
    raise SystemExit(main())
