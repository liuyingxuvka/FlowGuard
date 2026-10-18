# Development Process Flow

Reuse the current owner model and tests. Create a persistent scaffold only for a new
reusable boundary; apply the regression examples relevant to this change.
This stops "done" or "release" claims that rest on old test results. Each artifact
(code, test, model, requirement) has a current version; each evidence row records the
versions it ran on. The review catches a test that passed on code@1 while code is now
@2, a peer or unknown writer that changed a file after the run, a requirement edit that
should have re-run downstream checks, hidden skips, progress-only and failed runs
reported as current. It also computes a small re-run set. Map fingerprints make good versions.
## Use when

- You are about to claim done or release after several edits and test runs.
- Code, tests or the model changed after the last passing run.
- Another agent or person may have written the same files.
- An upstream component changed and you need the re-run list.
- A rough plan needs detail, routes compete, or an agent workflow needs a dry run (below).

## Do not use when

- You need to know if the code behaves correctly. Write a behavior model or real tests.
- You need to pick which tests cover a behavior. Use test-mesh or model-test-alignment.

## Inputs

- `python -m flowguard change`: changed files, affected components, tests and models to run.
- `python -m flowguard read --component ID` per affected component: `files`, `depends_on`,
  `tests`, `models`. Its `fingerprint` is in `.flowguard/map.json` (set by `map confirm ID`).
- In time order: edits, test and model runs, and who did each. For each run: command,
  status (`passed`, `failed`, `skipped`, `not_run`, ...), skipped count, versions it ran on.

## Steps

1. For an ordinary change, use its actual current test/native results and stop after affected validation.
   For real multi-stage dependencies reuse the owner; only a missing reusable boundary needs the model/runner/notes
   from `python -m flowguard template development-process-flow --write .`.
2. If the process-review branch is needed, update its existing plan (`model.py` only if persisted). One `ProcessArtifact` per component or file group;
   `current_version` = its map fingerprint (or a file hash). Set `owner` to make writes
   by any other `actor` a blocker.
   ```python
   from flowguard import (DevelopmentProcessPlan, ProcessArtifact, ProcessAction,
       ProcessEvidence, ValidationRequirement, FreshnessRule, PROCESS_EVIDENCE_PASSED,
       review_development_process_flow, derive_revalidation_plan)
   plan = DevelopmentProcessPlan("checkout-release",
       artifacts=(ProcessArtifact("checkout", "code", "fp:9c1e", owner="agent"),),
       actions=(ProcessAction("run-full", produced_evidence_ids=("full",)),
                ProcessAction("claim", action_type="claim_release", required_evidence_ids=("full",))),
       evidence=(ProcessEvidence("full", evidence_kind="full_validation",
           status=PROCESS_EVIDENCE_PASSED, covers_artifacts=("checkout",),
           covered_versions={"checkout": "fp:9c1e"}, produced_by_action_id="run-full",
           command="python -m pytest -q"),),
       full_validation_parent_receipt_ids=("full",))
   report = review_development_process_flow(plan)   # report.ok, .decision, .findings
   ```
   Actions are in time order. A write is `writes_artifacts`; a claim is `action_type`
   `claim_done` / `claim_release` / `publish` with `required_evidence_ids` or
   `required_validation_ids`. Use `actor="peer"` or `"unknown"` for writes not yours.
3. Add a `ValidationRequirement` per test or model from `change` output
   (`required_artifact_ids`, `required_evidence_kinds`, `command`). Add a `FreshnessRule`
   (`upstream_artifact_id`, `invalidates_artifact_ids`) per `depends_on` edge that matters.
4. Release: the plan needs exactly one id in `full_validation_parent_receipt_ids`. It must
   name a `ProcessEvidence` with `evidence_kind="full_validation"` that passed and is current.
5. Re-run list: `derive_revalidation_plan(plan)` returns `RevalidationRecommendation` rows (`requirement_id`,
   `command`, `freshness_gap_codes`) for declared requirements lacking current passing evidence.
6. Keep relevant business regressions. Any new/changed persistent runner must pass the good plan and reject relevant bad plans;
   register it in the owner's `models` and execute it once via `python -m flowguard map models <id>` (id = folder name).

### Plan detailing

Only for a plan-detailing need without a reusable owner, `python -m flowguard template plan-detailing --write .` gives a starter. Build a
`PlanDetail` (`goal`, `sources`, `artifacts`, `steps`, `validations`, `evidence`,
`side_effects`, `failure_branches`, `final_claim`) and call `review_plan_detail(plan)`
(`.ok`). `plan_detail_to_development_process(plan)` turns it into a `DevelopmentProcessPlan`.

### Process strategy

Only when routes compete. Set plan `process_optimization_reasons` (`explicit_request`,
`multiple_equivalent_routes`, `material_rework_risk`, `diagnostic_boundary_choice`). Build a
`ProcessOptimizationDecision` with a `ProcessOptimizationContract` and two or more
`ProcessOptimizationCandidate` rows; `review_process_optimization(decision)` rejects candidates
that miss the contract's outcomes or obligations and compares the rest by Pareto cost dominance
(a tie stays unresolved). It also needs `activation_reasons`, `input_revision`,
`current_evidence_ids`, `material_evidence_ids` and per-candidate `comparison_evidence_ids`.

### Agent workflow rehearsal

For a planned multi-skill run with side effects: `AgentWorkflowPlan(plan_id, task_summary,
inventory=SkillInventorySnapshot(...), selected_skill_names, skipped_candidate_skills, steps)`
with `AgentWorkflowStep` rows, then `review_agent_workflow_rehearsal(plan)` (`.ok`).

## What blocks

| Code | Meaning |
|---|---|
| `stale_evidence_after_artifact_change` | Evidence ran on an older version, or a later action wrote the artifact. |
| `test_changed_after_test_pass` | The test itself changed after it passed. |
| `unknown_writer_invalidates_evidence` | A peer or unknown actor wrote a covered artifact after the run. |
| `requirement_change_without_downstream_revalidation` | A `FreshnessRule` upstream changed after the run. |
| `process_action_writer_owner_mismatch` | The writing `actor` is not the artifact `owner`. |
| `release_claim_with_stale_evidence` | A claim depends on stale evidence. |
| `missing_required_revalidation` | A claim lacks current passing evidence. |
| `hidden_skipped_validation_claimed_pass` | Skips exist but `skipped_visible=False`. |
| `progress_only_validation_claimed_complete` | `progress_only=True`, or `background=True` without exit/result files. |
| `failed_validation_claimed_current` | Failed run used as evidence. |
| `full_validation_parent_not_unique` | Release claim without exactly one full-validation id. |
| `full_validation_parent_not_current` | That id is missing, not `full_validation`, or stale/failed. |

## Risk-specific regression examples

- Run before edit: `run-unit` then `edit-code`, claim uses `unit-pass` (stale, claim blocked).
- Peer write: after the run, `ProcessAction("sync", writes_artifacts=("checkout",), actor="peer")`.
- Hidden skips: `status="passed"`, `skipped_count=3`, `skipped_visible=False`.
- Release with only `evidence_kind="unit"` evidence, or no full-validation id.

## Done when

- [ ] Ordinary branch: report the affected commands' actual current results; no process scaffold is required.
- [ ] Process-review branch: the native review passes and relevant bad plans fail; any persistent runner is registered.
- [ ] `python -m flowguard change` is clean; for release only, use one complete frozen-source gate, locally or in CI.
- [ ] Your report lists what ran, what was skipped, and the re-run set.

## Limits

- A direct pytest/native result is sufficient for an ordinary run; use TestMesh only
  for real shard/parent aggregation. Progress alone never completes a test claim.

- It checks the rows you declare. It does not run tests or watch files; an undeclared write is invisible.
- Versions are only as good as you make them. A draft map component's fingerprint is empty until `map confirm ID`.
- The re-run set covers only declared requirements; with estimated costs it is a preferred cover, not a proven minimum.
- A passing release review is not proof of install, tag or publish; claim those separately.
