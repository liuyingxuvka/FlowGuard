# Field Lifecycle
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
   scaffold with `python -m flowguard template field-lifecycle --write .`.
   It writes owner `model.py`, `.flowguard/verification/owners/field_lifecycle/run_checks.py` and notes.
2. In the selected plan (`model.py` only if persisted): `from flowguard import FieldLifecyclePlan, FieldLifecycleRow, FieldLifecycleGroup, FieldProjection, review_field_lifecycle`.
3. One `FieldLifecycleRow(field_id, role=, lifecycle=, behavior_impacts=, reader_ids=, writer_ids=, owner_id=)` per field.
   - `role`: `state`, `routing`, `permission`, `feature_flag`, `schema_version`,
     `persisted`, `presentation`, `metadata`, `prompt_config`.
   - `lifecycle`: `active`, `new`, `old`, `replaced`, `deprecated`, `derived`, `archive_only`.
   - `behavior_impacts`: `state`, `routing`, `permission`, `side_effect`,
     `external_contract`, `schema`, `replay`, `migration` (or empty).
   - `coverage_disposition`: `modeled` (default), `delegated` (needs `delegated_owner_id`
     + `coverage_evidence_refs`) or `scoped` (needs `scoped_out_reason`). Presentation/metadata
     rows without a `scoped_out_reason` give a gap (see below).
4. Behavior-bearing rows get `projection=FieldProjection(projection_id, field_id, model_obligation_id=, code_contract_id=, required_test_kinds=, evidence_refs=)`.
   For a broad `claim_scope` (`full`, `release`, `production`, `broad`, ...),
   `evidence_refs` need a `gate:` ref, a `test:` ref when failure/negative test
   kinds are required, and a `replay:` ref when `replay` is a required test
   kind or a `behavior_impacts` entry.
5. Rows that are old, replaced, deprecated or set `replacement_field_id` or
   `old_field_ids`: set `disposition` to one of these:
   `deleted`, `blocked`, `migrated`, `delegated_to_new_field` or `same_contract_repaired` (each needs `disposition_evidence_refs`),
   `explicitly_preserved` (also `compatibility_intent`) or `out_of_scope`
   (needs `scoped_out_reason`). Unless compatibility was asked for, remove it.
6. `FieldLifecyclePlan(mesh_id, discovered_field_ids=, groups=, fields=, claim_scope=)`.
   For an "every field covered" claim add `require_complete_inventory=True`,
   `inventory_revision`, `inventory_fingerprint` (`sha256:` + 64 hex),
   `discovery_evidence_ids`, and per row `locations`, `default_semantics`,
   `absence_semantics`, `serialization_semantics`, `privacy_classification`,
   `content_fingerprint`.
7. Runtime-gateway evidence routes to `model_test_alignment`; closure routes to `development_process_flow`.
   Feed model-test alignment: `field_lifecycle_to_model_obligations(report)`, `field_lifecycle_to_code_contracts(report)`.
8. Review the current field plan and relevant broken cases. If persisting a runner, update its
   good/bad plans; it exits 0 only if the good plan passes, the broken one fails and
   obligations and code contracts were projected (shortened):

```python
correct = review_field_lifecycle(complete_field_lifecycle())
broken = review_field_lifecycle(broken_field_lifecycle())
ok = correct.ok and not broken.ok and field_lifecycle_to_model_obligations(correct)
```

9. If a persistent runner was created or changed, register it in the component's `models`;
   run the selected registered owner once with `python -m flowguard map models <id>`.
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
| `field_gate_evidence_missing` | Broad claim, projection has no `gate:` ref. |
| `field_negative_test_evidence_missing` | Broad claim, negative/failure kind required, no `test:` ref. |
| `field_replay_evidence_missing` | Broad claim, replay required, no `replay:` ref. |
| `field_delegation_incomplete` | `delegated` coverage without owner or evidence refs. |
| `field_scope_reason_missing` | `scoped` coverage without a reason. |
| `field_inventory_unexpected_row` | Complete inventory: a row is not in `discovered_field_ids`. |
| `field_inventory_duplicate_row` | Complete inventory: two rows share a field id. |

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
- Broad claim without trail: `claim_scope="full"`, projection with no `gate:`
  ref -> `field_gate_evidence_missing`.

## Done when
- [ ] The selected native review/check passes within its declared scope; partial gaps stay visible.
- [ ] Relevant broken plans fail with the expected code (assert the code, not only `not ok`).
- [ ] Every projected obligation has a real test, listed in the component's `tests`.
- [ ] No source file still reads a removed or renamed field (grep the old name).
- [ ] Any persistent runner is registered and executed once; `python -m flowguard change` is clean.
- [ ] Report which models and tests ran, the claim scope, and what was skipped.

## Limits
- It checks only the rows you declare. It does not scan or run code; a field
  you never discovered is invisible. Pair projections with real tests.
- Open gaps: a `replacement_field_id` naming no row still passes; a
  `scoped_out_reason` alone lets a behavior-bearing row skip its projection;
  duplicate rows are caught only with `require_complete_inventory=True`.
  Fingerprints are only format-checked, never recomputed.
- Vocabulary drift: `legacy_path_disposition_from_field_row` maps
  `delegated_to_new_field` to `unknown`; do not use it for delegated rows.
