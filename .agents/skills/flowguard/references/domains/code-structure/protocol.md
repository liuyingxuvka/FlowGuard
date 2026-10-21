# Code Structure Recommendation
Reuse the current owner model and tests. Create a persistent scaffold only for a new
reusable boundary; apply the regression examples relevant to this change.
Use this before you write code for a new feature. You start from a functional
model of the feature and decide which module owns each function block, state
item, field, side effect, config key and public entrypoint. The review catches
plans that break that rule: two modules that own the same side effect or state,
a field that is written but has no owner, an entrypoint given to a module that
is not in the plan, a plan with no source model or no test boundaries, or a
"shared kernel" built from two things that only look alike. After
the code exists, each recommended module becomes one component in
`.flowguard/map.json`.

## Use when

- A model-first feature is ready and you must choose modules, files and facades before coding.
- It is unclear which module should own a piece of state, a durable write or a field.
- You plan a facade plus adapters, or a shared kernel plus variant adapters.
- You want test boundaries per module that trace back to the model.

## Do not use when

- You are splitting an existing large file or module. Use structure-mesh.
- You do not yet know whether an owner already exists. Run existing-model first.
- You are renaming or retiring a field. Use field-lifecycle.
- There is no functional model yet. Build the model first; this route does not invent behavior.

## Inputs

- The functional model: its id, file path, function blocks, state, fields, side effects, entrypoints.
- `python -m flowguard read --find WORDS` to see components that already own nearby work.
- `python -m flowguard read --component ID` for the parent component: `files`, `entrypoints`,
  `state`, `side_effects`, `depends_on`, `tests`, `models`.
- Which fields each step reads and which it writes.
- The test you plan for each module (route test, state shape test, effect replay test).

## Steps

1. Reuse or update the current owner's native recommendation/review. Only for a missing
   reusable boundary, run `python -m flowguard template code-structure-recommendation --write .`
   This writes `.flowguard/models/owners/code_structure_recommendation/model.py` and
   `.flowguard/verification/owners/code_structure_recommendation/run_checks.py`.
   To use a feature name, rename both `code_structure_recommendation` directories and the
   `_MODEL_DIR` path inside `run_checks.py`.
2. Update the selected owner recommendation (`recommendation()` in a persisted `model.py`). API:
   ```python
   from flowguard import (CodeStructureRecommendation, TargetModuleRecommendation,
                          review_code_structure_recommendation)
   rec = CodeStructureRecommendation(
       "checkout-structure", source_model_id="checkout-model", parent_module_id="checkout",
       target_modules=(TargetModuleRecommendation("effects", path="checkout/effects.py",
           owns_side_effects=("write_order",), writes_fields=("field:mode",),
           validation_boundaries=("effect replay test",), rationale="durable writes only"),),
       side_effect_owner_map=(("write_order", "effects"),),
       function_block_map=(("PersistOrder", "effects"),),
       validation_boundaries=("effect replay test",), rationale="split by owner")
   report = review_code_structure_recommendation(rec)  # report.ok, report.findings
   ```
   Each `TargetModuleRecommendation` has `module_id`, `path`, `layer`, `owns_function_blocks`,
   `owns_state`, `owns_side_effects`, `owns_config`, `owns_fields`, `reads_fields`,
   `writes_fields`, `public_entrypoints`, `validation_boundaries`, `rationale`.
   The plan maps items to module ids with `function_block_map`, `state_owner_map`,
   `side_effect_owner_map`, `config_owner_map`, `field_owner_map`, `field_reader_map`,
   `field_writer_map`, `public_entrypoint_map` (tuples of `(item_id, module_id)`).
   Optional: `facade_module_id`, `shared_kernel_module_id`, `variant_adapter_module_ids`, and
   `canonical_relation_handoff` (a `CanonicalRelationHandoff` from `flowguard.canonical_relation`).
3. Keep the relevant broken recommendations (see below). A persistent `run_checks.py`, if needed,
   returns 0 only when the good plan passes and those broken variants fail.
4. If a persistent runner was created or changed, register it in the parent's `models` in `map.json`
   (`".flowguard/verification/owners/<id>/run_checks.py"`). Direct native review needs no new runner.
5. Execute a selected registered runner once with `python -m flowguard map models <id>`;
   do not also require a direct runner invocation for the same current checks.
6. Write the code. Then turn each target module into a map component: `files` = `path`,
   `responsibilities` = owned function blocks, `entrypoints` = `public_entrypoints`,
   `state` and `side_effects` = owned items, `tests` = the real tests for its
   `validation_boundaries`. Run `python -m flowguard map check`, `map lint`, then `map confirm ID`.

## What blocks

| Code | Meaning |
|---|---|
| `missing_source_model` | No `source_model_id`; the plan is not tied to a model. |
| `missing_function_block_map` | No function block is assigned to a module. |
| `missing_validation_plan` | No `validation_boundaries` for the plan. |
| `missing_module_rationale` | A target module has no reason for its grouping. |
| `duplicate_function_block_owner` | One function block has two owner modules. |
| `duplicate_side_effect_recommendation_owner` | Two modules own the same side effect. |
| `duplicate_state_recommendation_owner` | Two modules own the same state item. |
| `field_access_without_owner` | A field is read or written but no module owns it. |
| `function_block_owner_not_registered` | An item points at a module not in `target_modules` (same for `state_`, `side_effect_`, `field_writer_`, `entrypoint_owner_not_registered`). |
| `false_friend_relation_blocks_shared_structure` | The relation handoff has a false-friend relation; no shared module may come from it. |
| `shared_kernel_module_not_registered` | With a relation handoff: the shared kernel is not a target module (also `variant_adapter_module_not_registered`). |

After coding, map findings `file_multi_owner`, `file_unmapped` (check) and `duplicate_owner`
(lint) show where the code drifted from one owner per responsibility.

## Risk-specific regression examples

- Monolith: one module `checkout` with no rationale, empty `function_block_map`.
- Double writer: `side_effect_owner_map=(("write_order","orchestrator"),("write_order","effects"))`.
- Ownerless field: `field_writer_map=(("field:mode","effects"),)` with no `field_owner_map` entry.
- Ghost adapter: `public_entrypoint_map=(("POST /checkout","api"),)` where `api` is not a target module.

## Done when

- [ ] The selected direct native review or existing-owner model passes; relevant broken cases fail.
- [ ] Any new/changed persistent runner is registered and has one current `map models <id>` result.
- [ ] After coding, each module is one component with its tests listed; `map check` has no errors.
- [ ] `python -m flowguard change` is clean for the changed files.
- [ ] Your report names what ran, what was skipped and why.

## Limits

- It reviews the plan you declared. It does not read source code or prove the code follows the plan;
  `map check`, `map lint` and real tests do that.
- Not checked: the per-module `owns_*`, `reads_fields`, `writes_fields` lists (only the plan-level
  `*_map` pairs are), `facade_module_id`, a module that owns everything, two writers of one field,
  and the kernel/adapter ids when there is no `canonical_relation_handoff`.
