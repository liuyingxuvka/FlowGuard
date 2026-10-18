# Test Mesh
Reuse the current owner model and tests. Create a persistent scaffold only for a new
reusable boundary; apply the regression examples relevant to this change.
Test Mesh catches false green from large or slow test runs: two shards own the
same test or none does; a background job's progress log or live PID is reported
as a pass; counts do not add up (planned 500, executed 480, none marked not run);
skips hide inside a green summary; an old pass is reused after the code changed;
a routine run silently stands in for the release run.
## Use when
- The test suite is too large or slow to run whole on every change and must be split.
- Tests run in the background, in parallel shards, or with timeouts.
- A parent gate (CI job, release check) trusts child suites, or reuses an earlier pass.
- Some suites are release-only and may be deferred during routine work.
## Do not use when

- The test set is small and runs in one command. Just run it.
- You need to decide which tests match which model behavior. Use model-test-alignment.
- You need to split code or models, not tests. Use structure-mesh or model-mesh.

## Inputs

- `python -m flowguard change`: changed files, owning components, tests and models to run.
- `python -m flowguard read --component ID` per affected component: `tests`, `models`, `state`, `side_effects`.
- Test commands, node ids (`pytest --collect-only -q`), timeouts, release-only suites.
- Per finished suite: exit code, JUnit file, run id, planned/executed/failed/skipped/not-run.

## Steps

1. Run `python -m flowguard change` to choose the affected tests before execution.
   For a small selected set, run the exact printed commands once and stop here.
2. If the selected validation genuinely needs sharding, choose the packaged runner
   instead of first doing the same work directly:
   `python -m flowguard.pytest_shards_cli --root . --shards 4 --parallel-shards 4 --json`.
   It collects the whole suite and runs exact node ids in disjoint shards. It cannot
   select only `change` files; use direct pytest for those.
3. No hand-filled TestMesh model is needed for that runner's ordinary results. Only
   when a real parent trusts independent child suites/state/effect owners, scaffold
   `python -m flowguard template test-mesh --write .` and use the advanced API below.
4. In `model.py`: `from flowguard import TestMeshPlan, TestPartitionItem,
   TestSuiteEvidence, TestTargetSplitDerivation, TestResultReuseTicket, review_test_mesh,
   EVIDENCE_ABSTRACT_GREEN`.
5. One `TestPartitionItem(item_id, owner_suite_id=...)` per thing to test; one
   `TestSuiteEvidence` per suite or shard: `command`, `result_status`,
   `evidence_tier`, `evidence_current`, counts, `exit_code`, `result_path`, `run_id`,
   `background`, `progress_only`, `release_required`, `not_run_reason`, `owns_state`.
   If any suite sets `owns_state` or `owns_side_effects`, also set the split's
   `state_owner_fields` / `side_effect_owner_fields`, or the plan blocks.
6. With `planned_count/executed_count/failed_count/not_run_count`, also set
   `diagnostic_campaign_id` and `diagnostic_boundary` (`targeted`, `budgeted`, `declared_complete`).
7. Add `TestTargetSplitDerivation(source_model_id, target_suite_ids=...,
   covered_partition_item_ids=..., rationale=...)`; without it the plan blocks.
8. Set `decision_scope` (`routine` or `release`). `require_final_receipts=True` (real
   field; always applied to background suites) demands `run_id`, `terminal_status="passed"`,
   `exit_code=0` + `has_exit_artifact`, `result_path` + `has_result_artifact`, `result_fingerprint`,
   `artifact_version`, `verifier_version`, and `covered_obligation_ids` = the items it owns.
9. Reuse is strict: `result_reused=True` needs a `reuse_ticket` (`TestResultReuseTicket`)
   with a reason, previous evidence id, every fingerprint field, a terminal `"pass"`
   producer, matching execution owner ids, and
   `producer_fingerprints` equal to `current_fingerprints` (command, test_source,
   tested_artifact, dependencies, environment, result, coverage_scope); the suite
   also needs a `proof_artifact`. If you cannot fill these honestly, rerun the suite.
10. The template's `run_checks()` returns two reports (good plan, broken plan); the runner
    exits 0 only if the good one is ok and the broken one is not. Check your other broken variants too.
11. Add that runner path to the owning component's `models` in `.flowguard/map.json`,
    then run `python -m flowguard map models test_mesh`.

```python
report = review_test_mesh(TestMeshPlan(
    parent_suite_id="ci", decision_scope="routine",
    partition_items=(TestPartitionItem("orders", owner_suite_id="shard-1"),),
    child_suites=(TestSuiteEvidence("shard-1", command="pytest ...",
        result_status="passed", evidence_tier=EVIDENCE_ABSTRACT_GREEN,
        evidence_current=True, test_count=40, selected_count=40),),
    target_split_derivation=TestTargetSplitDerivation("ci-model",
        target_suite_ids=("shard-1",), covered_partition_item_ids=("orders",),
        rationale="one shard per component"),
))
print(report.ok, report.decision); print(report.format_text())
```

## What blocks

| Finding code | Meaning |
| --- | --- |
| `coverage_gap` | A partition item has no owning suite. |
| `duplicate_partition_owner` | Two suites own the same item. |
| `duplicate_state_owner` / `duplicate_side_effect_owner` | Two suites own the same state or side effect. |
| `missing_target_split_derivation` | No `TestTargetSplitDerivation` says how the split follows a model. |
| `diagnostic_campaign_count_inconsistent` | planned is not executed + not run. |
| `diagnostic_failed_count_exceeds_executed` | More failures than executed tests. |
| `diagnostic_false_completeness` | `declared_complete` but some tests did not run. |
| `background_incomplete` / `suite_progress_only` | Background or progress output counted as a result. |
| `hidden_skipped_tests` | Skips not visible in a green summary. |
| `stale_test_evidence` | The suite result is not current. |
| `missing_test_reuse_ticket` / `test_reuse_verifier_fingerprint_mismatch` | Reuse without a ticket, or a fingerprint changed since the earlier pass. |
| `release_suite_not_current` | Release scope with a release-only suite not run (a routine run only warns: `release_suite_deferred`). |

## Risk-specific regression examples

- Progress only: `background=True, progress_only=True`, no exit file: `suite_progress_only`
  and `background_incomplete`.
- Bad counts (campaign id and boundary set): `planned_count=5, executed_count=3, not_run_count=0`:
  `diagnostic_campaign_count_inconsistent`.
- Hidden skip, stale result: `skipped_count=2, skipped_visible=False, evidence_current=False`:
  `hidden_skipped_tests` and `stale_test_evidence`.
- Release gap: `decision_scope="release"`, a `release_required` suite with `result_status="not_run"`:
  `release_suite_not_current`.

## Done when

- [ ] Direct pytest/shard branch: report only that command's actual terminal results; no TestMesh model or second run.
- [ ] Real parent/child branch only: registered `map models test_mesh` passes; relevant broken plans fail with expected codes.
- [ ] Every selected test file is listed in some component's `tests` in map.json.
- [ ] `python -m flowguard change` shows no unmapped files and the listed tests pass.
- [ ] For a release claim, the final frozen source has one complete ordinary gate, locally or in exact-source CI.
- [ ] Report planned/executed/failed/not-run counts, what ran, what was deferred or skipped, and why.

## Limits
- `review_test_mesh` judges the facts you declare (counts, `evidence_current`, `result_fingerprint`).
  It does not run tests or read files. Feed it real numbers from the shard runner or pytest.
- `--resume-output` reuses only an exact terminal pass with matching source/input
  bytes, interpreter, dependencies, environment and command identity, plus matching
  recorder before/after input digests. Missing legacy identity or changed inputs
  discard that shard's reuse; its current native invocation runs once instead.
  Keep result directories outside source inputs (the default cache is excluded).
  Never resume for a final release gate.
- The shard runner always collects the whole suite; it cannot run only the files `change`
  selected. Run those directly with pytest.
- A green mesh shows the split is honest. It does not show the tests check the
  right behavior; pair it with model-test-alignment.
