# Contract Exhaustion
Reuse the current owner model and tests. Create a persistent scaffold only for a new
reusable boundary; apply the regression examples relevant to this change.
Catches bad inputs and value combinations that nobody wrote a reaction for.
You declare a finite boundary (a field, an input enum, a state, a payload) and
the review expands it into every canonical bad case: missing field, empty value,
wrong type, unknown enum, malformed input, stale evidence, replay, and so on.
You can also declare model-local axes and groups; the review builds their full
Cartesian product. Every generated case must have an oracle: the expected
reaction, such as "reject before side effect" or "block before downstream".
Example: declare field `amount` and you get three cases, each of which must be
rejected before any write happens.

## Use when

- A function or endpoint takes fields or enums and you need every bad value handled.
- A state x input product must be complete (no silent default branch).
- A real bug showed one missed bad value and you want its whole class covered.
- An expected list of members (handlers, variants, candidates) must not lose one.
- You need stable case ids to hand to tests (one test per case id).

## Do not use when

- The risk is ordering, retries or interleaving over time: use a state/workflow model.
- The question is whether tests really exercise the model: use model-test alignment.
- The boundary is open-ended (free text, unbounded lists) and you cannot bound it.
- You only want to know which field owns a value: use field lifecycle.

## Inputs

- `python -m flowguard read --find <words>` to find the owning component.
- `python -m flowguard read --component <id>`: read `entrypoints`, `state`,
  `side_effects`, `tests`, `models`.
- From the code: each input field and its allowed values, each state enum, and
  what must not happen on a bad value (the side effects listed in the map).
- The expected member list from its owner (registry, enum, spec), never from the
  subset the code happens to handle today.

## Steps

1. Scaffold: `python -m flowguard template contract-exhaustion --write .`
   It writes `.flowguard/models/owners/contract_exhaustion/model.py`,
   `.flowguard/verification/owners/contract_exhaustion/run_checks.py` and a notes file.
   For a second model, rename both directories and fix `_MODEL_DIR` in `run_checks.py`.
2. In `model.py`, declare the boundary with the real API:
   `from flowguard import ContractDimension, ContractAxis, ContractInteractionGroup, ContractOracle, ContractExhaustionPlan, review_contract_exhaustion`.
   - `ContractDimension(dimension_id, dimension_type, values=..., mutation_types=..., finite=True)`
     for single-field bad cases. Types include `field`, `input`, `state`, `payload`.
   - `ContractAxis(axis_id, model_id, values=...)` plus
     `ContractInteractionGroup(group_id, model_id, axis_ids=..., oracle_id=...)` for products.
   - `ContractOracle(oracle_id, expected_status=..., expected_message_fields=..., required_repair_fields=..., forbidden_downstream_steps=...)`.
   - `ContractExhaustionPlan(plan_id, dimensions=, axes=, interaction_groups=, oracles=, model_id=, claim_scope="routine")`.
3. Optional feeders turn other findings into seed cases (`seed_cases=`):
   `state_closure_cases_to_contract_cases`, `scenario_matrix_to_contract_cases`,
   `family_bad_case_seed_to_contract_cases`, `artifact_payload_cases_to_contract_cases`,
   `transition_coverage_to_contract_cases`, `model_mesh_closure_to_contract_cases`.
4. Keep actual broken plans relevant to the finite boundary (see examples below).
5. In `run_checks()`, return the good report and the bad reports, and update `main()`
   in `run_checks.py` to match (the template returns two reports). The runner must
   exit 0 only when the good plan is `ok` and every bad plan is not `ok`:

```python
def run_checks():
    good = review_contract_exhaustion(finite_plan())
    bad = [review_contract_exhaustion(p) for p in broken_plans()]
    return good, bad

# run_checks.py
good, bad = run_checks()
raise SystemExit(0 if good.ok and not any(r.ok for r in bad) else 1)
```

6. List the runner in the owning component's `models` in `.flowguard/map.json`:
   `".flowguard/verification/owners/contract_exhaustion/run_checks.py"`.
   Run it: `python -m flowguard map models contract_exhaustion` (exit 0 = pass).
7. Hand case ids to tests. `contract_exhaustion_to_test_mesh_cell_ids(report)` gives
   product ids (`cartesian:<model>:<group>:<n>`); it is empty for single-field cases.
   `contract_exhaustion_to_model_obligations(report)` covers every case
   (`contract_exhaustion:contract:<dimension>:<mutation>`). One test per required case.
8. Run `python -m flowguard change` and run the tests and models it lists.

## What blocks

| Code | Meaning |
|---|---|
| `contract_boundary_missing` | No dimensions, axes or seed cases declared. |
| `contract_oracle_missing` | A required generated case has no expected reaction. |
| `contract_oracle_unknown` | A group or case names an oracle id that is not declared. |
| `contract_dimension_unbounded` | `finite=False`. Blocks only if required, broad claim and `allow_unbounded_scoped=False`. |
| `contract_cartesian_axis_unknown` | A group uses an axis id that is not declared. |
| `contract_cartesian_axis_foreign_model` | A group uses an axis owned by another model. |
| `contract_cartesian_case_limit_exceeded` | Product exceeds the plan's `cartesian_case_limit` or the group's `max_combinations`. |
| `contract_oracle_feedback_fields_missing` | Actionable feedback required, oracle has no `expected_message_fields`. |
| `contract_oracle_repair_fields_missing` | Actionable feedback required, oracle has no `required_repair_fields`. |
| `expected_family_member_omitted` | An id in `expected_family_member_ids` is missing from `materialized_family_member_ids`. |
| `coverage_universe_missing` | A broad claim (`done`, `release`, `full`, ...) has no `ContractCoverageUniverse`. |
| `coverage_universe_item_missing` | The universe lists a dimension, axis or group that the plan never generated. |

`report.findings` holds the codes; `report.ok` is the pass/fail bit.

## Risk-specific regression examples

- Empty plan: `ContractExhaustionPlan("x")` must block with `contract_boundary_missing`.
- Product too big: same axes with `cartesian_case_limit` below the real product size
  must block with `contract_cartesian_case_limit_exceeded`.
- Foreign axis: one axis with a different `model_id` must block with
  `contract_cartesian_axis_foreign_model`.
- Dropped oracle: a group whose `oracle_id` is not in `oracles`, or a dimension with a
  custom mutation type and no oracle, must block with `contract_oracle_unknown` or
  `contract_oracle_missing`.

## Done when

- [ ] `python -m flowguard map models <id>` passes (good plan `ok`).
- [ ] Every broken plan fails with the expected code (assert the code, not only `not ok`).
- [ ] Each required case id has a test, and those tests are in the component's `tests`.
- [ ] The runner is listed in the component's `models` in `.flowguard/map.json`.
- [ ] `python -m flowguard change` is clean.
- [ ] Report which models and tests ran, the claim scope used, and what was skipped.

## Limits

- It only exhausts what you declared. A missing dimension or axis is a model gap
  the review cannot see. It does not run the code; pair every case id with a real test.
- With `ContractCoverageUniverse(allow_partitioned_product=True)`, the denominator is
  the plan's own declared groups and axes; `partition_group_coverage_incomplete` checks
  only against them. Nothing stops a plan shrinking its axes; review diffs to them.
- Broad claim scopes also require a coverage universe, composite handoff results and
  actionable oracles for every case; use `claim_scope="routine"` unless you supply them.
- Default oracles exist only for the built-in mutation types; custom types need an oracle.
