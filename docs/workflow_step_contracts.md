# Workflow Step Contracts

Workflow step contracts turn an important process step into a small explicit
ordering rule inside a FlowGuard model. A step can require receipts, produce
receipts, invalidate older receipts, and gate claim labels such as
`done_claimed` or `release_claimed`.

Here a "receipt" is only a label in the modeled workflow state: a marker that
says "this step's output is current in this trace". It is not a stored file or
an evidence record. The proof comes from running the model check, which
explores every trace and reports a counterexample when a step is skipped, out
of order, or relied on after it went stale.

When a workflow step is also a real-code node in a FlowGuard comparison, add
`runtime_node_ids` through `step_contract_metadata(...)` or
`WorkflowStepContract.runtime_node_ids`. This lets later runtime path evidence
and progress output point back to the same step contract instead of relying on
free-form logs.

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

The model still uses ordinary `Workflow`, `FunctionBlock`, `Trace`, and the
formal model-check behavior. The contracts compile to invariants, so the same
counterexample machinery catches a skipped step, a reversed order, a premature
claim, or a step output that a later step made stale.

If the workflow began as a rough plan, use `PlanDetailStep` rows first and
project them with `plan_detail_to_step_contracts(...)`. The projection preserves
prerequisite receipts, produced receipts, invalidated receipts, claim labels,
artifact ids, and validation skip policy so the step-contract model starts from
the same detailed plan the agent reviewed.

## How Modeled Receipts Work

- `requires_receipts`: receipts that must be current before this step counts.
- `produces_receipts`: receipts made current by this step.
- `invalidates_receipts`: receipts made stale by this step.
- `required_for_claims`: claim labels that require this step's receipts.
- `skip_policy`: whether a visible skipped step is forbidden, allowed, or
  allowed only with a reason.

If a contract has no explicit `produces_receipts`, completing the step produces
a default receipt with the same value as `step_id`.

These are all fields of `WorkflowStepContract` (and of `PlanDetailStep` for the
plan projection). They only shape the compiled invariants; nothing is written
to disk.

## Where It Connects

- `compile_step_contract_invariants(...)` feeds the formal model check and
  `run_model_first_checks(...)`.
- `review_step_contract_trace(...)` explains one concrete trace.
- `step_contracts_to_model_obligations(...)` feeds Model-Test Alignment.
- `step_contract_metadata_matches_rule(...)` lets conformance replay compare
  the step metadata the model expects with the metadata the real code emits.
- Pass the contracts as `FlowGuardCheckPlan(step_contracts=...)` so
  `run_model_first_checks(...)` compiles them together with the plan's own
  invariants.

Starter template (prints the files; add `--write .` to write them):

```powershell
python -m flowguard template workflow-step-contracts
```

Run the generated check script to prove the contracts catch the bad orders.
When the workflow code changes later, `python -m flowguard change` lists the
models and tests to rerun, and `python -m flowguard map check` reports stale map
fingerprints.
