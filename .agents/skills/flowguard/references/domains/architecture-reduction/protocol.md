# Architecture Reduction
Reuse the current owner model and tests. Create a persistent scaffold only for a new
reusable boundary; apply the regression examples relevant to this change.

Decide whether duplicate handlers, adapters, branches or modules can be merged
or removed without changing behavior. The bug class is "cleanup that silently
changes behavior": two handlers look the same and one is deleted, but it was
the only one that wrote a state field, fired a side effect, served a public
command, or held the last negative test for a legacy input. The review keeps a
candidate blocked or "keep" until the evidence shows observable behavior stays
the same. It never deletes code on a guess.

## Use when

- `python -m flowguard map lint` reports `duplicate_owner`, `possible_duplicate`, `duplicate_code` or `never_imported` and you want to act on it.
- You plan to merge two handlers, modules or validation paths that seem to do the same job.
- You want to collapse an adapter, alias, wrapper or fallback path into one owner.
- You want to remove a branch, state field or state phase that looks unused.

## Do not use when

- You need to split a large file or component (`large_file`, `large_component`). Use structure-mesh or code-structure.
- You plan a field rename or retirement. Use field-lifecycle.
- You are adding new behavior or do not yet know the owner. Use existing-model first.
- The change is formatting or a pure rename with no caller change.

## Inputs

- `python -m flowguard map lint --json`: the findings you will turn into candidates.
- `python -m flowguard read --component ID` for every component a finding names:
  `responsibilities`, `files`, `entrypoints`, `state`, `side_effects`, `depends_on`, `tests`, `models`.
- `python -m flowguard map impact <files>`: dependent components, and the tests and models to rerun.
- `python -m flowguard map check`: must show no `stale` component for the files you touch.
- The code of both sides of each duplicate, and `git rev-parse HEAD` as the inventory revision.

## Steps

1. Turn lint findings into candidate rows. One `ArchitectureReductionCandidate` per finding you act on:
   - `duplicate_owner` (two components claim one responsibility): `candidate_type="merge_modules"`, `target_action="merge"`.
   - `possible_duplicate`: start as `candidate_type="manual_review"`; read both components; promote to `merge_modules` only if they do the same job.
   - `duplicate_code` (identical bodies): `merge_handlers`, or `remove_duplicate_validation` for validators; `code_node_id="path.py:symbol"`.
   - `never_imported`: `target_action="remove"` with `proof_status="blocked_by_missing_evidence"` until you have searched for
     dynamic imports, plugin registration, console scripts and string references.
   - `entrypoint_unlisted`: first add it to the component's `entrypoints`. If it is a second path to the same behavior,
     record a `CompatibilitySurfaceClassification` with `public_entrypoints` set; preserve its observable contract.
   - `large_file` / `large_component`: not a candidate. Add `ArchitectureReductionTrigger("structure_mesh", reason)` instead.
   With no actionable candidate, report that result and stop. Start each candidate at `proof_status="risky_keep"`; raise it to `safe_by_equivalence` only when step 3 holds.
   Fill `affected_public_entrypoints`, `affected_state`, `affected_side_effects` from the map fields of the removed side.
2. Build the observable contract from the owning component: `public_entrypoints` = entrypoints,
   `observable_state` = state, `observable_side_effects` = side_effects, plus `observable_outputs`,
   `validation_boundaries`, `source_model_id` (first entry in `models`), `source_code_boundary_id` (component id), `rationale`.
3. Gather proof. Equivalence means: the component's tests pass before and after, every dependent component from
   `map impact` is updated, and no output, state field or side effect disappears. Put test paths in `evidence_refs`.
   If only some properties are shown, use `property_only_safe`; if traces must be replayed, `needs_conformance_replay`.
4. Optional: for internal steps of a kept route, add `ArchitectureReductionStepAssessment` rows
   (`action` retain/merge/delegate/remove/explicit_on_demand/unresolved, `caller_ids`, `caller_inventory_complete`,
   `safety_inventory_complete`, `safety_responsibility_ids`, `safety_owner_bindings`). Every step that is not `unresolved`
   needs `cost_evidence` (`ArchitectureReductionStepCost`) or blocks (`step_cost_evidence_missing`); cost never replaces proof.
5. Reuse the owner model; write a new runner only for a reusable reduction boundary. Set `inventory_current=False` if `map check` shows a touched component stale.
   ```python
   # .flowguard/verification/owners/<reduction_id>/run_checks.py
   from dataclasses import replace
   from flowguard import (ArchitectureReductionCandidate, ArchitectureReductionPlan,
       ArchitectureReductionTrigger, ObservableArchitectureContract, review_architecture_reduction)
   from flowguard.map.runner import run_owner
   REV = "<git HEAD>"
   contract = ObservableArchitectureContract(source_model_id="orders", source_code_boundary_id="orders",
       public_entrypoints=("app/api.py:create_order",), observable_outputs=("order_created",),
       observable_state=("orders.status",), observable_side_effects=("db.write_order",),
       validation_boundaries=("validate_order",), rationale="create order")
   cand = ArchitectureReductionCandidate(candidate_id="merge-validate", candidate_type="merge_handlers",
       code_node_id="app/orders.py:validate_v2", source_model_element="Validate", target_action="merge",
       proof_status="safe_by_equivalence", required_next_route="",
       rationale="map lint duplicate_code", evidence_refs=("tests/test_orders.py",), inventory_revision=REV)
   def plan(*cands): return ArchitectureReductionPlan(reduction_id="orders-cleanup", observable_contract=contract,
       candidates=cands, rationale="lint cleanup", inventory_revision=REV, inventory_source_ref=".flowguard/map.json",
       inventory_current=True, expected_candidate_ids=("merge-validate",), require_complete_inventory=True,
       companion_route_triggers=())
   def main():
       good = review_architecture_reduction(plan(cand)); print(good.format_text())
       bad = review_architecture_reduction(plan(replace(cand, target_action="remove", affected_state=("orders.status",))))
       return good.ok and not bad.ok
   if __name__ == "__main__": raise SystemExit(run_owner(main))
   ```
6. For a persistent runner created or changed in step 5, register it in the owner's `models`
   and run `python -m flowguard map models <reduction_id>` once; otherwise use the direct native review result.
7. Act on `report.target_actions` only when `report.ok` is True. `ready_candidate_ids` and `target_actions` can
   still list a candidate that has a blocker, so never use them alone. Follow a non-empty `required_next_route` only when its specific risk needs that owner.
8. After the code change: rerun `map lint` (the finding should be gone), update the map descriptions,
   `python -m flowguard map confirm <ids>`, then `python -m flowguard change`.

## What blocks

| Finding code | Meaning |
|---|---|
| `removes_observable_state` | A remove deletes a state field the contract calls observable. |
| `observable_side_effect_without_equivalence` | A remove/collapse touches an observable side effect without `safe_by_equivalence`. |
| `compatibility_surface_current_contract_blocks_contraction` | Removing or collapsing a surface that is still a current contract. |
| `compatibility_surface_negative_legacy_test_requires_evidence` | Removing a negative legacy test with no replacement evidence. |
| `compatibility_surface_archive_has_runtime_authority` | A surface marked archive-only still runs at runtime. |
| `facade_independent_business_authority` | A kept facade does real work instead of only delegating. |
| `blocked_by_missing_evidence` | Candidate has no proof yet. |
| `conformance_replay_required` | Candidate needs trace replay against real code before it can be ready. |
| `incomplete_candidate` / `missing_observable_contract` | Required fields are empty. |
| `expected_reduction_candidate_missing` / `candidate_inventory_stale` | A lint finding was dropped, or the map is stale. |
| `step_unique_safety_owner_removed` / `step_caller_inventory_incomplete` | A merged/removed step still owns a safety duty, or callers are not all known. |

`risky_candidate_kept` and `property_only_reduction` are warnings: the candidate is kept, not ready.

## Risk-specific regression examples

- Remove a duplicate handler that is the only writer of an observable state field: expect `removes_observable_state`.
- Delete a `never_imported` module that is loaded by a plugin registry, marked `blocked_by_missing_evidence`: expect `blocked_by_missing_evidence`.
- Drop a lint finding from the candidate list while it is in `expected_candidate_ids`: expect `expected_reduction_candidate_missing`.

## Done when

- [ ] Every acted-on lint finding is a candidate or has a reason in `scoped_candidate_reasons`.
- [ ] The selected direct review or existing-owner check passes; relevant broken cases return `ok=False`.
- [ ] Any persistent runner is registered; the component's `tests` list the equivalence tests.
- [ ] Those tests pass before and after the change.
- [ ] `python -m flowguard change` is clean; resolved findings disappear, while kept/blocked candidates stay visible.
- [ ] The report says which candidates ran, which stayed `risky_keep` or blocked, and what was skipped.

## Limits

- The review checks the rows you declared. It does not read code; a wrong `affected_state` gives a wrong pass. Pair it with real tests.
- `map lint` finds candidates by word overlap in `responsibilities` and identical AST bodies. Near-duplicates with different code are missed.
- `never_imported` cannot see dynamic imports or plugin loading. Treat it as a hint, not proof of dead code.
- Behavior retirement (`retire_behavior`) needs `proof_status="authorized_retirement"` and a full `ArchitectureRetirementProof`; without it the review blocks (`retirement_proof_missing`).
