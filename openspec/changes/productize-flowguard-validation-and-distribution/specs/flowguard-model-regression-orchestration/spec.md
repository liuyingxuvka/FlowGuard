## ADDED Requirements

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
