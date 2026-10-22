# Model Mesh

Reuse the current owner model and tests. Create a persistent scaffold only for a new
reusable boundary; apply the regression examples relevant to this change.

Use this when one flow is described by several models (a parent and its children).
The review catches gaps between the models, not bugs inside one model. Examples: two
child models both write `payment.status`; a parent item that no child owns; the payment
child renames its output `payment:settled` to `payment:captured` while the parent still
waits for the old name; a child output nobody consumes; a join that never gets all its
inputs; a retry loop with no progress rule. It also has a small explicit-table checker
(portable models) for state graphs, parent/child refinement and composition.

## Use when

- A flow crosses two or more models, or one model is too large and you split it.
- A child model changed its inputs, outputs, state, side effects or contracts.
- You need to know whether a child change needs only reattachment, a parent rerun or a sibling rerun.
- You claim the whole flow closes: every output consumed, every join complete, a normal exit reached.

## Do not use when

- There is only one model. Check it directly with its own model file.
- You are splitting tests or a test suite. Use test-mesh.
- You are splitting a large code file or module. Use code-structure.
- You need every input x state case of one leaf model. Use contract-exhaustion.

## Inputs

- `python -m flowguard read --component ID` for the parent and each child component:
  `entrypoints`, `state`, `side_effects`, `depends_on`, `tests`, `models`.
- `python -m flowguard map check`: a child whose code changed since `confirm` shows as `stale`.
- For each child: inputs it accepts, outputs it emits, state and side effects it owns,
  contracts it promises (`contracts_out`), functions it owns.
- The handoff tokens between children, and the joins, loops and exits in the parent flow.

## Steps

1. Reuse or update the owner's native mesh/review. Only for a missing reusable composition boundary,
   `python -m flowguard template model-mesh --write .` writes its model and runner (replace its `REPLACE_ME` anchor).
   To rename `model_mesh`, rename both owner folders and `_MODEL_DIR` in `run_checks.py`.
2. In the selected owner plan (`model.py` only if persisted), describe children and parent (API from `flowguard`):
   ```python
   from dataclasses import replace
   from flowguard.hierarchy import child_evidence_from_model
   from flowguard import (ChildReattachmentContract, HierarchyCoverageItem,
       HierarchyPartitionMap, ModelTargetSplitDerivation, MeshClosureModel, MeshClosureTransition,
       MeshClosureTerminal, review_hierarchical_mesh)
   pay = replace(child_evidence_from_model(".flowguard/models/payment.py", root="."),
       inputs_accepted=("order:placed",), outputs_emitted=("payment:settled",),
       side_effects_owned=("charge_card",))
   ship = replace(child_evidence_from_model(".flowguard/models/shipping.py", root="."),
       inputs_accepted=("payment:settled",), outputs_emitted=("shipment:sent",))
   closure = MeshClosureModel("checkout", root_entries=("order:placed",),
       transitions=(MeshClosureTransition("pay", consumes=("order:placed",),
           emits=("payment:settled",), consumer_model_id="payment"),
           MeshClosureTransition("ship", consumes=("payment:settled",),
               emits=("shipment:sent",), consumer_model_id="shipping")),
       terminals=(MeshClosureTerminal("done", consumes=("shipment:sent",)),))
   report = review_hierarchical_mesh(HierarchyPartitionMap("checkout",
       coverage_items=(HierarchyCoverageItem("charge", owner_model_id="payment"),),
       child_models=(pay, ship), target_split_derivation=ModelTargetSplitDerivation("checkout",
           target_child_model_ids=(pay.model_id, ship.model_id), covered_partition_item_ids=("charge",),
           state_owner_fields=pay.state_owned + ship.state_owned,
           side_effect_owner_fields=("charge_card",), rationale="Derived from checkout's model blocks"),
       reattachment_contracts=(ChildReattachmentContract("payment",
           expected_inputs=pay.inputs_accepted, expected_outputs=pay.outputs_emitted,
           expected_state_owned=pay.state_owned, expected_side_effects_owned=pay.side_effects_owned),),
       closure_model=closure), root=".")   # report.ok, report.decision, report.findings
   ```
   A contract must list the child's inputs and outputs (or set
   `allow_extra_inputs` / `allow_extra_outputs`). Mark loops `loop=True` and give them a `progress_rule` or `max_iterations`.
3. When a child changed, call `summarize_child_boundary_change(old_child, new_child,
   parent_contract=..., sibling_models=...)`. Its `propagation` is `unaffected`,
   `reattach_only`, `parent_rerun_required`, `sibling_rerun_required` or
   `split_review_required`. Pass the result in `boundary_changes=(...)`.
4. For an explicit state graph use the portable checker: `load_portable_model(path)` then
   `check_portable_model(model)`; parent/child with `check_refinement(parent, child,
   RefinementBinding(...))`; several models with `check_composition(models)`, or a joint
   system with `check_system_composition(system, request, models)`. `report.ok` means `status == "pass"`.
5. Keep relevant partition/reattachment regressions. A persistent runner, if needed, returns 0 only
   when the good mesh passes and relevant broken variants fail.
6. If a persistent runner was created or changed, register it in the parent's `models`; execute
   the selected registered runner once via `python -m flowguard map models <id>`, without a second direct run.
7. After a child edit, `python -m flowguard change` selects the full caller closure. `map impact --depth 2` is only a truncated diagnostic, not complete coverage.
   Re-confirm the stale child (`map confirm ID`) and re-run the parent mesh.

## What blocks

| Code | Meaning |
|---|---|
| `unknown_child_model` | A child ID is not a registered contract MODEL_ID (also `unknown_parent_model`). |
| `child_not_under_parent` | The real model-tree parent is not this parent model. |
| `coverage_gap` | A parent coverage item has no owner. |
| `duplicate_state_owner` | Two children own the same state field (also `duplicate_side_effect_owner`, `duplicate_function_owner`). |
| `missing_target_split_derivation` | Children exist but no `ModelTargetSplitDerivation` explains the split. |
| `child_reattachment_missing_output` | A child no longer emits an output the parent expects (also `_missing_input`, `_missing_state_owner`, `_missing_side_effect_owner`, `_missing_contract`, `_extra_input`, `_extra_output`). |
| `boundary_change_parent_rerun_required` | A child changed its handoff; rerun the parent (also `_sibling_rerun_required`: rerun siblings; `_reattachment_required`: parent has no reattachment contract for the changed child). |
| `mesh_closure_required` | An output is another child's input, but the parent has no closure model. |
| `unconsumed_child_output` | A child output is consumed by no transition, join or terminal. |
| `missing_join_point` | A join never receives all its required inputs. |
| `terminal_leak` | A terminal is reached while a required or child output is still unconsumed. |
| `loop_progress_required` | A `loop=True` transition has no `progress_rule`, `max_iterations`, `progress_tokens` or `blocker_tokens`. |

Portable checker finding ids: `invariant_forbidden_state_reachable`, `refinement_state_unmapped`,
`refinement_transition_unmapped`, `refinement_child_stale`, `composition_guarantee_conflict`.

## Risk-specific regression examples

- Renamed output: payment emits `payment:captured`, parent contract expects `payment:settled`
  (gives `child_reattachment_missing_output`, `unconsumed_child_output`, `unreachable_normal_exit`).
- Double owner: shipping also lists `payment.status` in `state_owned` (`duplicate_state_owner`).
- Endless retry: `MeshClosureTransition(..., loop=True)` with no progress rule (`loop_progress_required`).

## Done when

- [ ] The selected direct native mesh review or existing-owner check passes; relevant broken cases fail.
- [ ] Any new/changed persistent runner is registered and has one current `map models <id>` result.
- [ ] Each child component lists its real tests in `tests`; no child is `stale` in `map check`.
- [ ] `python -m flowguard change` is clean, and the parent and affected siblings were re-run.
- [ ] Your report names what ran, what was skipped, and which children were not re-checked.

## Limits

- With `root`, IDs come from the model tree and static anchored writes come from code.
  Inputs, outputs and effects remain declarations; run each child's own model and real tests.
- The closure model checks handoff tokens only, not what a child does with them.
- A green mesh says nothing about one child's internal paths. Check each child separately.
