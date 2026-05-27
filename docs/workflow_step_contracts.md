# Workflow Step Contracts

Workflow step contracts turn an important process step into a small explicit
receipt rule. A step can require receipts, produce receipts, invalidate older
receipts, and gate claim labels such as `done_claimed` or `release_claimed`.

Use this when the bug risk is not "the whole workflow is unknown" but "one
required part of the known workflow might be skipped, run too early, or counted
after its evidence is stale."

## Core Shape

```python
from flowguard import WorkflowStepContract

contracts = (
    WorkflowStepContract(
        "write_coverage_matrix",
        completion_labels=("coverage_matrix_written",),
        requires_receipts=("change_inventory", "risk_catalog"),
        produces_receipts=("coverage_matrix",),
    ),
    WorkflowStepContract(
        "run_full_regression",
        completion_labels=("full_regression_passed",),
        requires_receipts=("coverage_matrix",),
        produces_receipts=("full_regression",),
        required_for_claims=("done_claimed",),
    ),
)
```

The model still uses ordinary `Workflow`, `FunctionBlock`, `Trace`, and
`Explorer` behavior. The contracts compile to invariants, so the same
counterexample machinery catches a skipped step, a reversed order, a premature
claim, or a stale receipt.

## How Receipts Work

- `requires_receipts`: receipts that must be current before this step counts.
- `produces_receipts`: receipts made current by this step.
- `invalidates_receipts`: receipts made stale by this step.
- `required_for_claims`: claim labels that require this step's receipts.
- `skip_policy`: whether a visible skipped step is forbidden, allowed, or
  allowed only with a reason.

If a contract has no explicit `produces_receipts`, completing the step produces
a default receipt with the same value as `step_id`.

## Where It Connects

- `compile_step_contract_invariants(...)` feeds Explorer and
  `run_model_first_checks(...)`.
- `review_step_contract_trace(...)` explains one concrete trace.
- `step_contracts_to_validation_requirements(...)` feeds
  DevelopmentProcessFlow.
- `step_contracts_to_model_obligations(...)` feeds Model-Test Alignment.
- `step_contract_metadata_matches_rule(...)` lets conformance replay compare
  expected and observed receipt metadata.

Template:

```powershell
python -m flowguard workflow-step-contracts-template --output .
```
