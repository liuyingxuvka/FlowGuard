# Behavior Commitment and Primary Path
Tree operation: Review external promises at component entrypoints and the tests that prove them.
Reuse the current owner model and tests. Create a persistent scaffold only for a new
reusable boundary; apply the regression examples relevant to this change.
This capability catches two related bugs. First, an external promise (an API call, a CLI
command, a UI button, a documented workflow) that nobody owns: it has no source, no single
owner model, no tests, or it exists twice under two names. Second, a silent fallback: path A
fails and the code quietly runs path B, an old field, or a backup cache, and still reports
success. Example: order API A throws, the handler calls legacy API B and returns "ok";
the real bug in A stays hidden.
## Use when

- You add, change, rename, or remove a visible behavior (API, CLI, UI action, workflow step).
- A change touches code with more than one way to reach the same result (alias, wrapper,
  compatibility facade, legacy route, old field, cache).
- A bug fix is tempted to "try the old path if the new one fails".
- You plan a broad "done" or "release" claim about external behavior.

## Do not use when

- The change is only internal (helper, refactor, no visible effect): use plain modeling.
- A data field is added, renamed, or retired: use field-lifecycle.
- Tests are stale or too slow to rerun: use test-mesh.
- You need to merge or delete duplicate code paths: use architecture-reduction.

## Inputs

- `python -m flowguard read --find "<task words>"`, then `read --component <id>` for its
  entrypoints, state, side_effects, tests and models.
- The source of each promise: README section, API route, CLI help, UI screen, docs page.
- For every path to the same result: entrypoint, trigger, return, writes, failure behavior.
- Existing ledger file, if any: `.flowguard/behavior/inventory/ledger.json`.

## Steps

1. Look up existing promises first; never add a second promise for the same intent. Call
   `query_behavior_commitments_from_path(path, BehaviorLookupQuery(task_summary=..., changed_paths=...))`
   (also `tool_ids`, `error_signatures`). Use `primary_hits`; `related_hits` are context only.
   Status `blocked` means the ledger file could not be loaded, not "no promise".
2. Reuse the owner model. Only when the project has none for these promises, run
   `python -m flowguard template behavior-commitment --write .`: it writes the ledger
   `.flowguard/behavior/inventory/ledger.json` (the one place promises are kept) and one contract model,
   `.flowguard/models/behavior_commitment.py`, whose `REPLACE_ME` anchors fail until they name your code.
3. Edit `ledger.json` (`BehaviorCommitmentLedger`, rows under the top-level `ledger` key):
   - each `source_surfaces` row: `surface_id`, `source_ref` (path, `path#anchor`, or a
       bounded glob), `coverage_disposition` (`modeled`, `delegated`, `scoped`), `commitment_ids`.
   - each `commitments` row: `commitment_id`, `business_intent_id` (one per exact promise),
     `behavior_plane` (`product_runtime`, `agent_operation`, `development_process`),
     `actor_kind`, `trigger`, `expected_result`, `expected_terminal`, `failure_boundary`,
     `source_surface_ids`, one `primary_owner_model_id`, and the anchors
     `entrypoints` (`path:Symbol` of the code that keeps the promise) and `tests` (`tests/x.py:test_name`).
   - set `change_mode`: `bootstrap_ledger`, `add_behavior`, `change_behavior`,
     `remove_or_replace_behavior`, `coverage_gap_backfill` or `model_miss_check`.
   - an alias, wrapper or second UI for the same promise maps to the same commitment.
4. In the model, `plan()` returns `BehaviorPlan(ledger, authority)`: the loaded ledger and, for a path-sensitive
   promise, its `PrimaryPathAuthorityPlan`: one `PrimaryPathContract` per intent (`business_path_id`,
   `business_intent_id`, `primary_entrypoint_id`, `owner_model_id`, `owner_code_contract_id`, `expected_terminal`,
   `failure_policy`) and one `FallbackPathCandidate` per other path (`candidate_path_id`, `fallback_for_path_id`,
   `candidate_surface`, `candidate_trigger`, `candidate_behavior`, `invokes_on_primary_failure`,
   `returns_success_after_primary_failure`, `disposition`). Write paths as `path:Symbol` where they are code.
5. Write the change as named edits: `add_commitment(plan, commitment or id, *surfaces)` (a surface is linked both
   ways), `retire_commitment(plan, id, reason)`, `add_path(plan, path)` (a primary path with
   `replaces_primary_path_id` replaces that one), `retire_path(plan, path_id, reason)` (default disposition
   `delete`). Edits replace by id, so applying one twice changes nothing.
   - `build_explorer()`: `behavior_commitment_explorer(plan, EDITS, explore=[...])` explores every sequence of
     the edits. `review_behavior_commitment_ledger` (with the project root: anchors exist),
     `review_primary_path_authority` and a static scan of the real tests (each test file of a commitment imports
     or calls one of its entrypoints, and each entrypoint is imported or called by one of its tests) must accept
     every plan reached.
   - `broken_variants()`: one wrong edit per risk of this change (examples below).
   - `conformance()`: `behavior_commitment_code_facts(target_plan, anchors=IMPLEMENTED_BY)`: entrypoints and
     tests exist and touch each other, the primary entrypoint exists, a facade that delegates imports or calls
     it, and a path retired with disposition `delete` is gone from the code.
   A one-off direct check without a model:
   `review_behavior_commitment_ledger(load_behavior_commitment_ledger(path), project_root=".")` and
   `review_primary_path_authority(plan)`.
6. Its components come from `IMPLEMENTED_BY`; add `COMPONENTS` or `PARENT` only to place it elsewhere.
   Run `python -m flowguard map models behavior_commitment`.

7. After the code change, save the target ledger with `write_behavior_commitment_ledger(path, target_plan.ledger)`,
   update the map descriptions, `python -m flowguard map confirm <ids>`, then `python -m flowguard change`.

## What blocks
| Finding code | Meaning |
|---|---|
| `primary_failure_masked_by_fallback_success` | Path A failed, path B ran and returned success. |
| `old_field_or_backup_cache_masks_primary_failure` | An old field or cache hides a broken primary path. |
| `manual_recovery_auto_invoked` | A manual repair path runs automatically on failure. |
| `duplicate_primary_runtime_authority` | Two primary paths serve the same exact intent. |
| `facade_contains_business_logic` | A compatibility facade writes state or decides results instead of delegating. |
| `duplicate_exact_intent_commitment` | Two commitments describe the same promise. |
| `delegate_commitment_forbidden` | An alias or wrapper was registered as its own commitment. |
| `source_surface_missing_commitment` | A promise source maps to no commitment. |
| `commitment_missing_primary_owner` | A commitment has no single owner model. |
| `commitment_anchor_missing` | With the project root: an entrypoint or test anchor names no real code. |
| `commitment_test_misses_entrypoint` | Model kit: a commitment's test never imports or calls its entrypoint. |

## Risk-specific regression examples
- A-fails-B-succeeds: a `FallbackPathCandidate` with `candidate_trigger="primary_failure"`,
  `invokes_on_primary_failure=True`, `returns_success_after_primary_failure=True`.
  Must give `primary_failure_masked_by_fallback_success`.
- Old field (`candidate_surface="old_field"`, `candidate_trigger="missing_field"`,
  `returns_success_after_primary_failure=True`, `disposition="unknown"`). Must give
  `old_field_or_backup_cache_masks_primary_failure` and `fallback_candidate_unknown_disposition`.
- Ledger with a copied commitment under a new `commitment_id` but the same
  `business_intent_id`. Must give `duplicate_exact_intent_commitment`.
- A commitment that names a second entrypoint (an old API) that none of its tests calls. Must give
  `commitment_test_misses_entrypoint`.

## Done when
- [ ] The intended edits pass; each relevant known-bad edit fails; unrelated variants are not new obligations.
- [ ] The code facts hold: anchors exist, tests touch their entrypoints, facades call the primary path.
- [ ] Each changed promise has one commitment, one owner model and tests; the model is listed in `models`.
- [ ] `python -m flowguard change` is clean, and the listed tests and models ran.
- [ ] You report what ran, what was skipped, and why.

## Limits
- It checks the rows you declare. A path you never list as a candidate is not found.
  Pair it with real tests that force the primary path to fail.
- The test scan is static and per file: an import counts, a test file that tests several things passes for any
  of them, and a call through a helper in another file is not seen. "Delegates" means the facade's file imports
  or calls the primary entrypoint, not that it returns the same result.
- There is no CLI command for the promise lookup; use the Python call in step 1.
