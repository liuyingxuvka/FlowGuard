"""Template text for FlowGuard workflow step contracts route."""

from __future__ import annotations

WORKFLOW_STEP_CONTRACTS_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: Declare workflow steps as receipt-producing contracts so later steps and done/release claims cannot skip required work.
Guards against: skipped mandatory steps, wrong step order, premature completion claims, stale receipts after invalidation, and progress-only evidence being treated as completion.
Use before editing: Update this workflow step contract model when adding, removing, reordering, or renaming required process steps, receipts, claims, or validation evidence.
Run: python .flowguard/workflow_step_contracts/run_checks.py
"""

from __future__ import annotations

from flowguard import (
    Trace,
    TraceStep,
    WorkflowStepContract,
    review_step_contract_trace,
    step_contracts_to_model_obligations,
    step_contracts_to_validation_requirements,
)


CONTRACTS = (
    WorkflowStepContract(
        "write_change_inventory",
        completion_labels=("change_inventory_written",),
        produces_receipts=("change_inventory",),
        description="The work starts by listing the changed files and affected behavior.",
    ),
    WorkflowStepContract(
        "write_coverage_matrix",
        completion_labels=("coverage_matrix_written",),
        requires_receipts=("change_inventory",),
        produces_receipts=("coverage_matrix",),
        description="Coverage matrix maps changed behavior to model, replay, and test evidence.",
    ),
    WorkflowStepContract(
        "run_regression",
        completion_labels=("regression_passed",),
        requires_receipts=("coverage_matrix",),
        produces_receipts=("full_regression",),
        required_for_claims=("done_claimed",),
        required_test_kinds=("replay", "edge_path"),
        description="Full regression is required before the done claim.",
    ),
)


def step(label: str) -> TraceStep:
    return TraceStep(
        external_input=label,
        function_name="development_step",
        function_input=label,
        function_output=label,
        old_state=(),
        new_state=(),
        label=label,
    )


def good_trace() -> Trace:
    return Trace(
        steps=(
            step("change_inventory_written"),
            step("coverage_matrix_written"),
            step("regression_passed"),
            step("done_claimed"),
        )
    )


def broken_trace() -> Trace:
    return Trace(
        steps=(
            step("change_inventory_written"),
            step("coverage_matrix_written"),
            step("done_claimed"),
        )
    )


def run_checks():
    good = review_step_contract_trace(good_trace(), CONTRACTS)
    broken = review_step_contract_trace(broken_trace(), CONTRACTS)
    process_requirements = step_contracts_to_validation_requirements(CONTRACTS)
    model_obligations = step_contracts_to_model_obligations(CONTRACTS)
    return good, broken, process_requirements, model_obligations
'''

WORKFLOW_STEP_CONTRACTS_RUN_CHECKS_TEMPLATE = '''"""Run the workflow step contracts template checks."""

from __future__ import annotations

from model import run_checks


def main() -> int:
    good, broken, process_requirements, model_obligations = run_checks()
    print("=== flowguard workflow step contracts ===")
    print(good.format_text())
    print()
    print(broken.format_text())
    print(f"process_requirements: {len(process_requirements)}")
    print(f"model_obligations: {len(model_obligations)}")
    return 0 if good.ok and not broken.ok and process_requirements and model_obligations else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

WORKFLOW_STEP_CONTRACTS_NOTES_TEMPLATE = """# FlowGuard workflow step contracts

## FlowGuard Risk Purpose Header

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: Make required workflow steps explicit as receipts that later steps and claims must consume.
Guards against: skipped mandatory steps, premature done/release claims, stale receipts after invalidation, and hidden workflow shortcuts.
Use before editing: Update these contracts whenever the project changes required steps, evidence receipts, claim labels, or validation scope.
Run: python .flowguard/workflow_step_contracts/run_checks.py

## How to read this template

Each `WorkflowStepContract` is a small promise:

- `requires_receipts` says what must already be current.
- `produces_receipts` says what this step proves when it completes.
- `invalidates_receipts` says which older receipts stop being current.
- `required_for_claims` says which done, release, archive, or publish labels need this receipt.
- `skip_policy` says whether a skipped step is forbidden or must carry an explicit reason.

The same contract list can feed model exploration, DevelopmentProcessFlow
validation requirements, Model-Test Alignment obligations, and conformance
replay metadata checks.
"""

__all__ = [
    'WORKFLOW_STEP_CONTRACTS_MODEL_TEMPLATE',
    'WORKFLOW_STEP_CONTRACTS_RUN_CHECKS_TEMPLATE',
    'WORKFLOW_STEP_CONTRACTS_NOTES_TEMPLATE',
]
