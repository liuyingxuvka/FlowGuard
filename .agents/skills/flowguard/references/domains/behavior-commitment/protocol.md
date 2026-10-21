# Behavior Commitment and Primary Path
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
2. If no ledger exists, run `python -m flowguard template behavior-commitment-ledger --write .`
   It writes `ledger.json`, a loader `model.py` and a runner `run_checks.py`.
3. Edit `ledger.json` (`BehaviorCommitmentLedger`, rows under the top-level `ledger` key):
   - each `source_surfaces` row: `surface_id`, `source_ref` (path, `path#anchor`, or a
       bounded glob), `coverage_disposition` (`modeled`, `delegated`, `scoped`), `commitment_ids`.
   - each `commitments` row: `commitment_id`, `business_intent_id` (one per exact promise),
     `behavior_plane` (`product_runtime`, `agent_operation`, `development_process`),
     `actor_kind`, `trigger`, `expected_result`, `expected_terminal`, `failure_boundary`,
     `source_surface_ids`, one `primary_owner_model_id`, `evidence.test_evidence_ids`, and the anchors
     `entrypoints` (`path:Symbol` of the code that keeps the promise) and `tests` (`tests/x.py:test_name`).
   - set `change_mode`: `bootstrap_ledger`, `add_behavior`, `change_behavior`,
     `remove_or_replace_behavior`, `coverage_gap_backfill` or `model_miss_check`.
   - an alias, wrapper or second UI for the same promise maps to the same commitment.
4. For each changed path-sensitive promise, reuse its existing primary-path owner and plan.
   Only for a missing reusable boundary, run `python -m flowguard template primary-path-authority --write .`;
   fill/update `PrimaryPathAuthorityPlan`: one `PrimaryPathContract` per intent
   (`business_path_id`, `business_intent_id`, `primary_entrypoint_id`, `owner_model_id`,
   `owner_code_contract_id`, `expected_terminal`, `failure_policy`) and one
   `FallbackPathCandidate` per other path (`candidate_path_id`, `fallback_for_path_id`,
   `candidate_surface`, `candidate_trigger`, `candidate_behavior`, `invokes_on_primary_failure`,
   `returns_success_after_primary_failure`, `disposition`).
5. Review the plan and the ledger separately; a fallback finding in the plan blocks the change.

```python
from flowguard import (review_primary_path_authority, review_behavior_commitment_ledger,
    load_behavior_commitment_ledger)
ppa = review_primary_path_authority(plan)            # ppa.ok, ppa.findings
ledger = load_behavior_commitment_ledger(".flowguard/behavior/inventory/ledger.json")
report = review_behavior_commitment_ledger(ledger, project_root=".")   # anchors must exist in the code
print(report.format_text())
```

6. If using the ledger scaffold, replace the starter `source_ref` values (`README.md#usage`,
   `api/run-primary-workflow`) with real ones. Keep relevant failure assertions; add other variants
   only for this change's risks, reusing existing owner tests.
7. If a persistent runner was created or changed, register it in the owner's `models`, then run
   each affected registered runner id once: `python -m flowguard map models <runner-id>`
   (exit 0 = pass). The unchanged scaffold ids are `behavior_commitment_ledger` for
   the ledger and `primary_path_authority` for the primary-path plan; use the actual
   directory id if renamed, not the component id. If no persistent runner changed,
   use the selected direct native review or existing-owner check without creating a runner.

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

## Risk-specific regression examples
- A-fails-B-succeeds: a `FallbackPathCandidate` with `candidate_trigger="primary_failure"`,
  `invokes_on_primary_failure=True`, `returns_success_after_primary_failure=True`.
  Must give `primary_failure_masked_by_fallback_success`.
- Old field (`candidate_surface="old_field"`, `candidate_trigger="missing_field"`,
  `returns_success_after_primary_failure=True`, `disposition="unknown"`). Must give
  `old_field_or_backup_cache_masks_primary_failure` and `fallback_candidate_unknown_disposition`.
- Ledger with a copied commitment under a new `commitment_id` but the same
  `business_intent_id`. Must give `duplicate_exact_intent_commitment`.

## Done when
- [ ] The good plan and the good ledger review with `ok=True` and no findings.
- [ ] Each relevant broken variant fails with its expected code; unrelated variants are not new obligations.
- [ ] Each changed promise has one commitment, one owner model and tests; any persistent runner is registered.
- [ ] `python -m flowguard change` is clean, and the listed tests and models ran.
- [ ] You report what ran, what was skipped, and why.

## Limits
- It checks the rows you declare. A path you never list as a candidate is not found.
  Pair it with real tests that force the primary path to fail.
- There is no CLI command for the promise lookup; use the Python call in step 1.
