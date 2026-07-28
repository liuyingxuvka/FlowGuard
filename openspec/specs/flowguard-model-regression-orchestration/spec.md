# flowguard-model-regression-orchestration Specification

## Purpose
Define complete, observable, fail-closed model regression execution with exact per-model freshness and reusable terminal evidence.
## Requirements
### Requirement: Explicit Model Regression Manifest
The repository SHALL maintain a versioned regression manifest that accounts for every discovered FlowGuard model directory and executable model entry. Each record SHALL declare model id, runner command, tier, timeout, shard-safety, mutation policy, watched inputs, expected artifacts, and either execution status or an explicit evidence-backed exclusion.

#### Scenario: Model has executable main but no run_checks file
- **WHEN** discovery finds an executable model entry absent from the manifest
- **THEN** inventory validation fails even if `rglob("run_checks.py")` would omit it

#### Scenario: Manifest names missing model
- **WHEN** a manifest record points to a model that no longer exists
- **THEN** inventory validation fails with a missing-model finding

### Requirement: Tiered And Selectable Regression Execution
The regression orchestrator SHALL support fast, focused, and full tiers plus model filters and deterministic shards. Only the full tier with all required manifest records terminal and current MAY support release validation.

#### Scenario: Fast tier passes
- **WHEN** the fast tier completes successfully
- **THEN** output claims fast-tier confidence only and does not imply full model closure

#### Scenario: Full tier skips required runner
- **WHEN** a required full-tier model is skipped or not run
- **THEN** full regression status is not pass and names the missing terminal

### Requirement: Bounded Observable Runner Execution
Every runner SHALL have a configured timeout, progress events, output isolation, captured stdout/stderr, cancellation behavior, and a terminal evidence receipt. Background or parallel execution SHALL be permitted only for manifest entries declared shard-safe and output-isolated.

#### Scenario: Runner exceeds timeout
- **WHEN** a runner exceeds its declared timeout
- **THEN** the orchestrator terminates it, emits a timeout terminal receipt, and continues or blocks according to tier policy

#### Scenario: Unsafe runner is scheduled in parallel
- **WHEN** a runner is not shard-safe or shares an output path
- **THEN** the scheduler serializes or rejects that execution rather than racing it

### Requirement: Non-Mutating Default
Default regression execution MUST NOT modify tracked repository files. A mutating runner SHALL require explicit authorization and an isolated output or worktree policy; mutation discovered in default mode MUST fail the run.

#### Scenario: Runner rewrites result json in default mode
- **WHEN** a runner modifies a tracked `result.json` during default execution
- **THEN** the orchestrator marks a mutation-policy failure and full validation is blocked

### Requirement: Exact-Current Per-Model Reuse
The model regression orchestrator SHALL independently resolve and verify one
terminal receipt per required model against the model's own declared content,
runner, local inputs, purpose, dependencies, toolchain, environment, inventory,
and obligations. A model with an exact-current receipt SHALL be reused without
starting its runner.

#### Scenario: Identical full model request repeats
- **WHEN** every required model has an independently verified exact-current terminal-success receipt
- **THEN** the parent model result composes those receipts and starts zero model runners

#### Scenario: One model input changes
- **WHEN** one model's declared local input changes and no declared relation or shared dependency expands the affected closure
- **THEN** only that model executes and unrelated model receipt ids remain reusable

### Requirement: Local Model Instance Identity
A model instance fingerprint SHALL contain only that model's logical id, model
content, runner, declared local inputs, purpose binding, and consumed
schema/tool identities. The model-system source revision and Git revision SHALL
remain snapshot-level provenance and SHALL NOT alter unrelated instance
fingerprints.

#### Scenario: Unrelated model changes
- **WHEN** model A changes and model B's local functional inputs are identical
- **THEN** model B retains the same instance fingerprint while the candidate snapshot fingerprint changes

### Requirement: Fail-Closed Model Impact Planning
Before execution, every changed functional input SHALL map to an exact model,
relation, shared dependency, or explicit snapshot-only owner. Missing,
ambiguous, or conflicting mappings MUST block the model plan and MUST NOT fall
back to running all models.

#### Scenario: Unknown model input appears
- **WHEN** a governed source path has no declared impact owner
- **THEN** plan status is blocked, no model producer starts, and the missing mapping is reported

### Requirement: Model Receipt Preservation After Parent Failure
Terminal-success model receipts SHALL remain independently reusable when a
sibling model or parent composition fails, provided their exact functional
identities remain current.

#### Scenario: One model fails then is repaired
- **WHEN** a full model parent records one failed model and later only that model's inputs change
- **THEN** successful sibling receipts are reused and only the repaired model executes
