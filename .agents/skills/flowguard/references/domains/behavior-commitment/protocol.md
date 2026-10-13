# Behavior Commitment and Primary Path

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
   It writes `ledger.json`, a loader `model.py`, a runner `run_checks.py` and notes.
3. Edit `ledger.json` (`BehaviorCommitmentLedger`, rows under the top-level `ledger` key):
   - each `source_surfaces` row: `surface_id`, `source_ref` (path, `path#anchor`, or a
       bounded glob), `coverage_disposition` (`modeled`, `delegated`, `scoped`), `commitment_ids`.
   - each `commitments` row: `commitment_id`, `business_intent_id` (one per exact promise),
     `behavior_plane` (`product_runtime`, `agent_operation`, `development_process`),
     `actor_kind`, `trigger`, `expected_result`, `expected_terminal`, `failure_boundary`,
     `source_surface_ids`, one `primary_owner_model_id`, `evidence.test_evidence_ids`,
     `path_authority.path_sensitive`.
   - set `change_mode`: `bootstrap_ledger`, `add_behavior`, `change_behavior`,
     `remove_or_replace_behavior`, `coverage_gap_backfill` or `model_miss_check`.
   - an alias, wrapper or second UI for the same promise maps to the same commitment.
4. For each path-sensitive promise, run `python -m flowguard template primary-path-authority --write .`
   and fill `PrimaryPathAuthorityPlan`: one `PrimaryPathContract` per intent
   (`business_path_id`, `business_intent_id`, `primary_entrypoint_id`, `owner_model_id`,
   `owner_code_contract_id`, `expected_terminal`, `failure_policy`) and one
   `FallbackPathCandidate` per other path (`candidate_path_id`, `fallback_for_path_id`,
   `candidate_surface`, `candidate_trigger`, `candidate_behavior`, `invokes_on_primary_failure`,
   `returns_success_after_primary_failure`, `disposition`).
5. Review the plan, then store `binding.to_dict()` as the commitment's `path_authority`.
   Set `primary_path_id` on its source surfaces to the same path id, or the ledger review
   reports `source_surface_primary_path_mismatch`.

```python
from flowguard import (review_primary_path_authority, review_behavior_commitment_ledger,
    behavior_path_binding_from_primary_path_report, load_behavior_commitment_ledger)
ppa = review_primary_path_authority(plan)            # ppa.ok, ppa.findings
binding = behavior_path_binding_from_primary_path_report(
    ppa, business_intent_id="intent:submit-order",
    behavior_commitment_id="commitment:submit-order")
ledger = load_behavior_commitment_ledger(".flowguard/behavior/inventory/ledger.json")
report = review_behavior_commitment_ledger(ledger, project_root=".")
print(report.format_text())
```

6. Pass `project_root` so source files are checked live (missing file, missing anchor,
   changed content). After an accepted source change, `refresh_behavior_commitment_source_inventory(ledger, root)`
   returns an updated ledger (it raises if a source is missing); save it with `write_behavior_commitment_ledger(path, ledger)`.
7. The ledger runner calls the review without `project_root`. Add it after you replace the
   starter `source_ref` values (`README.md#usage`, `api/run-primary-workflow`) with real ones.
   The primary-path runner already asserts the first two broken variants below; add the rest.
8. List the runners in the owning component's `models` in `.flowguard/map.json`, e.g.
   `.flowguard/verification/owners/primary_path_authority/run_checks.py`. Run one with
   `python -m flowguard map models primary_path_authority` (exit 0 = pass).

## What blocks

| Finding code | Meaning |
|---|---|
| `primary_failure_masked_by_fallback_success` | Path A failed, path B ran and returned success. |
| `old_field_or_backup_cache_masks_primary_failure` | An old field or cache hides a broken primary path. |
| `manual_recovery_auto_invoked` | A manual repair path runs automatically on failure. |
| `duplicate_primary_runtime_authority` | Two primary paths serve the same exact intent. |
| `facade_contains_business_logic` | A compatibility facade writes state or decides results instead of delegating. |
| `primary_path_runtime_evidence_not_current` | The plan needs run evidence and the primary path's proof is not a current pass. |
| `duplicate_exact_intent_commitment` | Two commitments describe the same promise. |
| `delegate_commitment_forbidden` | An alias or wrapper was registered as its own commitment. |
| `source_surface_missing_commitment` | A promise source maps to no commitment. |
| `commitment_missing_primary_owner` | A commitment has no single owner model. |
| `commitment_primary_path_blocked` | A path-sensitive commitment points at a blocked path review. |
| `source_surface_content_fingerprint_stale` | The source file changed since the ledger was updated. |

## Known-bad cases to include

- A-fails-B-succeeds: a `FallbackPathCandidate` with `candidate_trigger="primary_failure"`,
  `invokes_on_primary_failure=True`, `returns_success_after_primary_failure=True`.
  Must give `primary_failure_masked_by_fallback_success`.
- Old field (`candidate_surface="old_field"`, `candidate_trigger="missing_field"`,
  `returns_success_after_primary_failure=True`, `disposition="unknown"`). Must give
  `old_field_or_backup_cache_masks_primary_failure` and `fallback_candidate_unknown_disposition`.
- Ledger with a copied commitment under a new `commitment_id` but the same
  `business_intent_id`. Must give `duplicate_exact_intent_commitment`.
- A path-sensitive commitment whose binding has `ppa_ok=False`. Must give
  `commitment_primary_path_blocked`.

## Done when

- [ ] The good plan and the good ledger review with `ok=True` and no findings.
- [ ] Every broken variant fails with its expected code.
- [ ] Each changed promise has one commitment, one owner model and tests, listed with the runners in `.flowguard/map.json`.
- [ ] `python -m flowguard change` is clean, and the listed tests and models ran.
- [ ] You report what ran, what was skipped, and why.

## Limits

- It checks the rows you declare. A path you never list as a candidate is not found.
  Pair it with real tests that force the primary path to fail.
- `runtime_evidence_state="current_pass"` is your claim; the review does not run code or open proof files.
- Live audit checks that source files exist and have not changed. It does not check
  that the code still does what the commitment says.
- There is no CLI command for the promise lookup; use the Python call in step 1.
