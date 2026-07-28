## 1. Model And Baseline

- [x] 1.1 Add and run a task-specific FlowGuard model for prediction freeze, real replay, candidate decision, and rollback invariants.
- [x] 1.2 Preserve a baseline inventory of pre-existing worktree changes and confirm all owned implementation files are initially unmodified.

## 2. Prediction And Revision

- [x] 2.1 Implement immutable task model version and prediction snapshot records with deterministic fingerprints.
- [x] 2.2 Bind official prediction replay to the existing conformance engine and expose prediction identity on the report.
- [x] 2.3 Implement proposed, accepted, rejected, and rolled-back task revision transitions with required replay enforcement.

## 3. Production Evidence

- [x] 3.1 Make status-only passing conformance block production confidence while preserving explicit non-pass statuses.
- [x] 3.2 Remove expected-output inputs from the job-matching production adapter and production methods.
- [x] 3.3 Replace first-occurrence exact-path checking with complete occurrence-ordered comparison per runtime run.
- [x] 3.4 Bind occurrence-specific terminal, state-write, and side-effect checks in exact-path mode.

## 4. Guidance And Tests

- [x] 4.1 Update the clean model-first conformance protocol with prediction, independent adapter, replay, and task-local revision rules.
- [x] 4.2 Add focused tests for status-only blocking, prediction/report binding, revision accept/reject/rollback, adapter independence, repeated nodes, occurrence behavior, and multiple runs.
- [x] 4.3 Run the new FlowGuard model and affected unit/integration tests; fix every owned failure.

## 5. Repository Validation

- [x] 5.1 Run OpenSpec verification for this change and resolve artifact/spec/task findings.
  - Evidence: `openspec validate bind-task-prediction-to-real-replay --strict` and `openspec validate --all --strict` passed; this installed OpenSpec CLI does not expose a separate `verify` subcommand.
- [x] 5.2 Run the repository's affected FlowGuard model checks, project/suite checks, and SkillGuard project/target checks without installing user-level skills.
  - Evidence: the task-local model and 45 affected tests passed. The repository-wide and SkillGuard checks were executed but remain blocked by separately owned, pre-existing worktree changes recorded in the final handoff.
- [x] 5.3 Compare final worktree state with the baseline and report exact overlap with pre-existing dirty files, skipped checks, blockers, and claim boundary.
  - Evidence: the only intentional overlap with a pre-existing dirty file is `.flowguard/model-regression-manifest.json`; the new ignored `.flowguard/task_local_prediction_replay/` files must be force-added by the integrator.
