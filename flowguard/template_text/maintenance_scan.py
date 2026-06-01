"""Template text for FlowGuard maintenance scan router."""

from __future__ import annotations

MAINTENANCE_SCAN_RUN_TEMPLATE = '''"""Run a small FlowGuard maintenance scan example.

This template is a thin router. It identifies maintenance actions and routes
them to existing FlowGuard capabilities; it does not run those capabilities.
"""

from flowguard import (
    MAINTENANCE_ARTIFACT_CODE,
    MAINTENANCE_ARTIFACT_MODEL,
    MAINTENANCE_SCAN_DECISION_CLEAR,
    MAINTENANCE_SCAN_DECISION_SCOPED,
    MAINTENANCE_SIGNAL_LARGE_MODULE,
    MAINTENANCE_SIGNAL_REDUCIBLE_BRANCH,
    MaintenanceChangedArtifact,
    MaintenanceScanPlan,
    MaintenanceSignal,
    review_maintenance_scan,
)


def run_case(name, plan, expected_decision, expected_routes=()):
    report = review_maintenance_scan(plan)
    print(f"{name}: {report.decision}")
    if report.decision != expected_decision:
        print(report.format_text())
        return False
    routes = {action.route_id for action in report.actions}
    missing = set(expected_routes) - routes
    if missing:
        print(report.format_text())
        print(f"missing expected routes: {sorted(missing)!r}")
        return False
    return True


def main():
    clear = MaintenanceScanPlan("clear-docs", claim_scope="bounded")
    alignment_needed = MaintenanceScanPlan(
        "model-code-change",
        claim_scope="done",
        changed_artifacts=(
            MaintenanceChangedArtifact("checkout-model", MAINTENANCE_ARTIFACT_MODEL, ".flowguard/checkout/model.py"),
            MaintenanceChangedArtifact("checkout-code", MAINTENANCE_ARTIFACT_CODE, "checkout.py"),
        ),
    )
    structure_needed = MaintenanceScanPlan(
        "structure-pressure",
        signals=(
            MaintenanceSignal("dup-branch", MAINTENANCE_SIGNAL_REDUCIBLE_BRANCH),
            MaintenanceSignal("large-module", MAINTENANCE_SIGNAL_LARGE_MODULE),
        ),
    )

    ok = all(
        (
            run_case("clear", clear, MAINTENANCE_SCAN_DECISION_CLEAR),
            run_case("alignment_needed", alignment_needed, MAINTENANCE_SCAN_DECISION_SCOPED, ("model_test_alignment",)),
            run_case(
                "structure_needed",
                structure_needed,
                "maintenance_scan_actions_required",
                ("architecture_reduction", "structure_mesh_maintenance"),
            ),
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

MAINTENANCE_SCAN_NOTES_TEMPLATE = """# FlowGuard Maintenance Scan Notes

Use this scaffold when a FlowGuard-managed project needs a thin maintenance
router after a non-trivial change.

## Boundary

The maintenance scan only decides which existing FlowGuard routes need work.
It does not replace Model-Test Alignment, Architecture Reduction, StructureMesh,
ModelMesh, TestMesh, DevelopmentProcessFlow, or AgentWorkflowRehearsal.

## Typical Signals

- model/code/test changed together;
- stale evidence, changed guidance, or release artifacts;
- skipped candidate FlowGuard route without accepted scope;
- duplicate branch, pass-through adapter, removable state, or duplicate
  validation;
- large module, public API split, oversized model, stale child model evidence,
  slow tests, progress-only tests, or broad validation.

## Completion Rule

If the scan reports a required action, route to the owning FlowGuard specialist
and use that specialist's evidence before claiming broad confidence. A clear
scan is not model/test/replay validation by itself.
"""

__all__ = [
    "MAINTENANCE_SCAN_RUN_TEMPLATE",
    "MAINTENANCE_SCAN_NOTES_TEMPLATE",
]
