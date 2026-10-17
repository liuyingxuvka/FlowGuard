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
- You are splitting a large code file or module. Use structure-mesh.
- You need every input x state case of one leaf model. Use contract-exhaustion.

## Inputs

- `python -m flowguard read --component ID` for the parent and each child component:
  `entrypoints`, `state`, `side_effects`, `depends_on`, `tests`, `models`.
- Each child component's `fingerprint` in `.flowguard/map.json`. Use it as the child's
  evidence id. `python -m flowguard map check` reports a changed child as `stale`.
- For each child: inputs it accepts, outputs it emits, state and side effects it owns,
  contracts it promises (`contracts_out`), functions it owns.
- The handoff tokens between children, and the joins, loops and exits in the parent flow.

## Steps

1. `python -m flowguard template model-mesh --write .` writes
   `.flowguard/models/owners/model_mesh/model.py`, `.flowguard/verification/owners/model_mesh/run_checks.py`
   and a notes file. To rename `model_mesh`, rename both folders and the `_MODEL_DIR` path in `run_checks.py`.
2. In `model.py`, describe each child and the parent (API from `flowguard`):
   ```python
   from flowguard import (ChildModelEvidence, ChildReattachmentContract, HierarchyCoverageItem,
       HierarchyPartitionMap, ModelTargetSplitDerivation, MeshClosureModel, MeshClosureTransition,
       MeshClosureTerminal, EVIDENCE_ABSTRACT_GREEN, review_hierarchical_mesh)
   pay = ChildModelEvidence("payment", evidence_id="<map fingerprint>", inputs_accepted=("order:placed",),
       outputs_emitted=("payment:settled",), state_owned=("payment.status",),
       side_effects_owned=("charge_card",), evidence_tier=EVIDENCE_ABSTRACT_GREEN)
   closure = MeshClosureModel("checkout", root_entries=("order:placed",),
       transitions=(MeshClosureTransition("pay", consumes=("order:placed",),
           emits=("payment:settled",), consumer_model_id="payment"), ...),
       terminals=(MeshClosureTerminal("done", consumes=("shipment:sent",)),),
       required_outputs=("shipment:sent",))
   report = review_hierarchical_mesh(HierarchyPartitionMap("checkout",
       coverage_items=(HierarchyCoverageItem("charge", owner_model_id="payment"), ...),
       child_models=(pay, ship), target_split_derivation=ModelTargetSplitDerivation("checkout",
           target_child_model_ids=("payment", "shipping"), covered_partition_item_ids=("charge", "ship"),
           state_owner_fields=("payment.status",), side_effect_owner_fields=("charge_card",), rationale="..."),
       reattachment_contracts=(ChildReattachmentContract("payment", consumed_evidence_id="<fingerprint>",
           expected_inputs=("order:placed",), expected_outputs=("payment:settled",),
           expected_state_owned=("payment.status",)),),
       closure_model=closure))   # report.ok, report.decision, report.findings
   ```
   Set `evidence_tier` to at least `required_evidence_tier` (default `abstract_green`); the
   default `candidate_only` blocks. A contract must list the child's inputs and outputs (or set
   `allow_extra_inputs` / `allow_extra_outputs`). Mark loops `loop=True` and give them a `progress_rule` or `max_iterations`.
3. When a child changed, call `summarize_child_boundary_change(old_child, new_child,
   parent_contract=..., sibling_models=...)`. Its `propagation` is `unaffected`,
   `reattach_only`, `parent_rerun_required`, `sibling_rerun_required` or
   `split_review_required`. Pass the result in `boundary_changes=(...)`.
4. For an explicit state graph use the portable checker: `load_portable_model(path)` then
   `check_portable_model(model)`; parent/child with `check_refinement(parent, child,
   RefinementBinding(...))`; several models with `check_composition(models)`, or a joint
   system with `check_system_composition(system, request, models)`. `report.ok` means `status == "pass"`.
5. Retain the relevant real partition/reattachment regression from the table below. `run_checks.py` must return 0 only when the good mesh
   passes and every broken variant fails.
6. Run `python .flowguard/verification/owners/<id>/run_checks.py`. List that path in the parent
   component's `models` in `.flowguard/map.json`, then run `python -m flowguard map models <id>`.
7. After a child edit: `python -m flowguard change` (or `map impact --depth 2`) lists dependents.
   Re-confirm the stale child (`map confirm ID`), copy its new fingerprint into the child's
   `evidence_id` and the parent's `consumed_evidence_id`, and re-run the parent mesh.

## What blocks

| Code | Meaning |
|---|---|
| `coverage_gap` | A parent coverage item has no owner. |
| `duplicate_state_owner` | Two children own the same state field (also `duplicate_side_effect_owner`, `duplicate_function_owner`). |
| `missing_target_split_derivation` | Children exist but no `ModelTargetSplitDerivation` explains the split. |
| `child_reattachment_stale_evidence` | The parent consumed an old child evidence id (fingerprint). |
| `child_reattachment_missing_output` | A child no longer emits an output the parent expects (also `_missing_input`, `_missing_state_owner`, `_missing_side_effect_owner`, `_missing_contract`, `_extra_input`, `_extra_output`). |
| `boundary_change_parent_rerun_required` | A child changed its handoff; rerun the parent (also `_sibling_rerun_required`: rerun siblings; `_reattachment_required`: parent did not consume the new evidence id). |
| `mesh_closure_required` | Children hand off outputs but the parent has no closure model. |
| `unconsumed_child_output` | A child output is consumed by no transition, join or terminal. |
| `missing_join_point` | A join never receives all its required inputs. |
| `terminal_leak` | A terminal is reached while a required or child output is still unconsumed. |
| `loop_progress_required` | A `loop=True` transition has no `progress_rule`, `max_iterations`, `progress_tokens` or `blocker_tokens`. |
| `insufficient_evidence_tier` | A child's `evidence_tier` is below the parent requirement. |

Portable checker finding ids: `invariant_forbidden_state_reachable`, `refinement_state_unmapped`,
`refinement_transition_unmapped`, `refinement_child_stale`, `composition_guarantee_conflict`.

## Risk-specific regression examples

- Renamed output: payment emits `payment:captured`, parent contract expects `payment:settled`
  (gives `child_reattachment_missing_output`, `unconsumed_child_output`, `unreachable_normal_exit`).
- Double owner: shipping also lists `payment.status` in `state_owned` (`duplicate_state_owner`).
- Stale reattach: child `evidence_id` changed, contract still has the old one (`child_reattachment_stale_evidence`).
- Endless retry: `MeshClosureTransition(..., loop=True)` with no progress rule (`loop_progress_required`).

## Done when

- [ ] `run_checks.py` exits 0: the good mesh passes and every broken variant fails.
- [ ] The runner is in the parent component's `models`; `python -m flowguard map models <id>` passes.
- [ ] Each child component lists its real tests in `tests`; no child is `stale` in `map check`.
- [ ] `python -m flowguard change` is clean, and the parent and affected siblings were re-run.
- [ ] Your report names what ran, what was skipped, and which children were not re-checked.

## Limits

- `strict=True` or full/release rejects explicit child parent/scope values that disagree with the parent; empty optional values are allowed.

- It checks the boundaries you declare. It does not read code; a child that lies about its
  outputs passes. Pair it with each child's own model and real tests.
- The closure model checks handoff tokens only, not what a child does with them.
- Evidence ids are plain strings. Only your discipline ties them to the map fingerprint;
  the map does not store parent/child links between models.
- A green mesh says nothing about one child's internal paths. Check each child separately.
