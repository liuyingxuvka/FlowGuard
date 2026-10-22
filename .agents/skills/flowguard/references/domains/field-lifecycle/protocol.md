# Field Lifecycle
Tree operation: Change state fields declared by several nodes.
Reuse the current owner model and tests. Create a persistent scaffold only for a new
reusable boundary; apply the regression examples relevant to this change.
Catches half-done field changes: a renamed field that a reader still uses, a
routing or permission flag whose new behavior no obligation or test covers, an
old field that survives because nobody chose to delete, block or migrate it.
You write one row per field (owner, readers, writers, role, lifecycle, impact).
The review blocks when a discovered field has no row, a behavior-bearing field
has no model/code projection, or an old field has no closing disposition.
Example: after renaming `old_mode` to `mode`, `old_mode` needs a disposition.
## Use when
- A change adds, removes, renames, migrates or re-defaults a payload, schema,
  config, prompt, persisted or UI field (including aliases and fallbacks).
- A bug came from a missing, stale or wrongly read field.
- A flag or enum field selects a route, permission or side effect, or you must
  show every field of a boundary is accounted for.

## Do not use when

- You need every bad value of a field handled: use contract exhaustion.
- You need to know whether tests really exercise obligations: use model-test
  alignment (this capability only feeds it).
- The risk is ordering or retries over time: use a state/workflow model.

## Inputs

- `python -m flowguard read --find <field words>`, then
  `python -m flowguard read --component <id>`: read `files`, `entrypoints`,
  `state`, `side_effects`, `tests`, `models`.
- From the code (dataclasses, schemas, config, payloads): every field in the
  boundary with owner, locations, readers, writers, default, absence/null
  meaning, serialization, and behavior impact. Take the list from the code.
- For a rename or removal: every place that still reads the old name (`grep`).

## Steps
1. Reuse or update the owner's current field lifecycle/review. Only for a missing reusable boundary,
   scaffold with `python -m flowguard template field-lifecycle --write .`. It writes one contract model,
   `.flowguard/models/field_lifecycle.py`, whose `REPLACE_ME` anchors fail until they name your real code and test.
2. In the selected plan: `from flowguard import FieldLifecyclePlan, FieldLifecycleRow, FieldLifecycleGroup, FieldProjection, review_field_lifecycle`.
3. One `FieldLifecycleRow(field_id, role=, lifecycle=, behavior_impacts=, reader_ids=, writer_ids=, owner_id=)` per field.
   - `role`: `state`, `routing`, `permission`, `feature_flag`, `schema_version`,
     `persisted`, `presentation`, `metadata`, `prompt_config`.
   - `lifecycle`: `active`, `new`, `old`, `replaced`, `deprecated`, `derived`, `archive_only`.
   - `behavior_impacts`: `state`, `routing`, `permission`, `side_effect`,
     `external_contract`, `schema`, `replay`, `migration` (or empty).
   - `coverage_disposition`: `modeled` (default), `delegated` (needs `delegated_owner_id`
     + `coverage_evidence_refs`) or `scoped` (needs `scoped_out_reason`). Presentation/metadata
     rows without a `scoped_out_reason` give a gap (see below).
4. Behavior-bearing rows get `projection=FieldProjection(projection_id, field_id, model_obligation_id=, code_contract_id=, required_test_kinds=)`.
5. Rows that are old, replaced, deprecated or set `replacement_field_id` or
   `old_field_ids`: set `disposition` to one of these:
   `deleted`, `blocked`, `migrated`, `delegated_to_new_field` or `same_contract_repaired` (each needs `disposition_evidence_refs`),
   `explicitly_preserved` (also `compatibility_intent`) or `out_of_scope`
   (needs `scoped_out_reason`). Unless compatibility was asked for, remove it.
6. `FieldLifecyclePlan(mesh_id, discovered_field_ids=, groups=, fields=)`. Every id in
   `discovered_field_ids` needs a row; take the list from the code, not from the rows you wrote.
7. Runtime-gateway evidence routes to `model_test_alignment`.
   Feed model-test alignment: `field_lifecycle_to_model_obligations(report)`, `field_lifecycle_to_code_contracts(report)`.
8. In the model, write the change as named plan edits (`add_field_row`, `replace_field_row`):
   `build_explorer()` returns `field_lifecycle_explorer(plan, EDITS, explore=[...])` (the review must accept
   every plan the edits reach), `broken_variants()` explores one wrong edit (for example an old field dropped
   without disposition), and `conformance()` returns
   `field_lifecycle_code_facts(target_plan, OWNED_FILES, anchors=IMPLEMENTED_BY)`: a deleted field has no
   reference left in `OWNED_FILES`, its replacement is present, every declared location still holds its field.
   During planning, set `DESIGN_ONLY = "<reason>"` and pass `planned="DESIGN_ONLY" in globals()` to the code-facts helper.
   Keep `IMPLEMENTED_BY` on today's real code; at least one real fact must hold. Planned failures are explicit,
   never include broken anchors, and require `DESIGN_ONLY`. After the edit, update anchors and remove the marker.
9. Its components come from `IMPLEMENTED_BY`; add `COMPONENTS` or `PARENT` only to place it elsewhere.
   Run `python -m flowguard map models field_lifecycle`.

10. Run `python -m flowguard change`; execute selected checks not already current, rerunning affected checks after edits.

## What blocks
| Code | Meaning |
|---|---|
| `field_lifecycle_missing_field_row` | A discovered field has no row. |
| `behavior_field_projection_missing` | Behavior-bearing field with no projection and no scoped-out reason. |
| `field_role_invalid` | A row's role is outside exported `FIELD_ROLES`. |
| `field_lifecycle_invalid` | A row's lifecycle is outside exported `FIELD_LIFECYCLES`. |
| `field_behavior_impact_invalid` | Any behavior impact is outside exported `FIELD_IMPACTS`. |
| `field_model_obligation_missing` | A projection has no `model_obligation_id`. |
| `field_code_contract_missing` | A projection has no `code_contract_id`. |
| `old_field_disposition_open` | Old/replaced/deprecated field with no closing disposition and evidence. |
| `field_delegation_incomplete` | `delegated` coverage without owner or evidence refs. |
| `field_scope_reason_missing` | `scoped` coverage without a reason. |

Gaps (`non_behavior_field_scope_missing`, `field_group_missing`) give decision
`field_lifecycle_scoped` with `ok` = `allow_scoped_confidence` (default `True`): check `report.decision`.

## Risk-specific regression examples
- Rename left open: `old_mode` with `lifecycle="replaced"`, `replacement_field_id`, no disposition -> `old_field_disposition_open`.
- Dropped row: a field in `discovered_field_ids` with no row -> `field_lifecycle_missing_field_row`.
- Unprojected flag: `role="routing"`, `behavior_impacts=("routing",)`, no
  projection -> `behavior_field_projection_missing`.
- Unknown vocabulary: `behavior_impacts=("permisssion",)` blocks with
  `field_behavior_impact_invalid`; unknown role or lifecycle blocks with its
  corresponding code, including for scoped or delegated coverage.

## Done when
- [ ] The selected native review/check passes within its declared scope; partial gaps stay visible.
- [ ] Relevant broken plans fail with the expected code (assert the code, not only `not ok`).
- [ ] Every projected obligation has a real test, listed in the component's `tests`.
- [ ] No source file still reads a removed or renamed field (`field_lifecycle_code_facts` checks `OWNED_FILES`).
- [ ] Any persistent runner is registered and executed once; `python -m flowguard change` is clean.
- [ ] Report which models and tests ran, the claim scope, and what was skipped.

## Limits
- The review checks only the rows you declare; `field_lifecycle_code_facts` reads `OWNED_FILES`
  statically and runs nothing. A field you never discovered is invisible. Pair projections with real tests.
- Open gaps: a `replacement_field_id` naming no row still passes; a
  `scoped_out_reason` alone lets a behavior-bearing row skip its projection;
  two rows with the same field id are not reported.
