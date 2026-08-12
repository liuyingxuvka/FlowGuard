# long-check-observability Specification
## Purpose
This capability defines how FlowGuard keeps long-running validation visible, bounded, and evidence-backed instead of treating background progress as completion.
## Requirements
### Requirement: Background checks record durable evidence
FlowGuard skill guidance SHALL require long-running background checks to record complete stdout and stderr, terminal exit status, metadata, and result artifacts by default. Complete streams MAY be retained as deterministic compressed content-addressed objects with bounded human-readable tails; guidance MUST NOT require redundant raw, combined, and parsed full-payload copies when the compressed objects are verifiable and recoverable.

#### Scenario: Long check is run in the background
- **WHEN** an agent runs a long FlowGuard check outside the foreground session
- **THEN** the agent records complete stdout/stderr object descriptors, exit status, metadata, and the terminal result under a declared evidence root

#### Scenario: Compressed stream is used
- **WHEN** complete stdout or stderr is retained as a compressed object
- **THEN** its descriptor records logical hash and size, storage hash and size, compression, and recoverable object path

### Requirement: Reports cite concrete completion evidence
FlowGuard skill guidance SHALL require final task reports to cite the log root, exit code, last update time, and proof-reuse status for long-running checks.

#### Scenario: Agent reports a completed long check
- **WHEN** an agent claims a long FlowGuard check completed
- **THEN** the report names the log artifacts, exit code, last update time, and whether the result was newly executed or reused from a valid proof

### Requirement: Progress remains observability only
FlowGuard skill guidance SHALL explain that progress lines are liveness evidence only and MUST NOT replace executable check results.

#### Scenario: Progress reaches one hundred percent
- **WHEN** a progress stream reaches `100%`
- **THEN** the agent still waits for the check result and exit status before claiming pass or fail

### Requirement: Custom runners declare progress boundaries
FlowGuard skill guidance SHALL require agents to distinguish direct Explorer progress from legacy or custom runners that only emit final reports.

#### Scenario: Custom runner lacks live progress
- **WHEN** a project-specific runner bypasses direct Explorer progress
- **THEN** the agent reports that the runner is final-report-only unless that runner implements its own stderr progress

### Requirement: Long checks distinguish proof reuse from progress reuse
Long-running FlowGuard checks SHALL distinguish completed result reuse from
progress output reuse for model and test regressions.

#### Scenario: Completed result can be reused
- **WHEN** a model or test regression result already has final exit/status and
  result artifacts
- **AND** the appropriate reuse ticket proves the current scope still matches
- **THEN** the long-check report MAY mark the result as validly reused

#### Scenario: Progress output cannot be reused as pass evidence
- **WHEN** a background check has only progress output or missing final result
  artifacts
- **THEN** the long-check report SHALL treat it as liveness evidence only, not
  completion evidence

### Requirement: Aggregate local model regression runner
FlowGuard SHALL provide a tracked command that discovers present `.flowguard/**/run_checks.py` files, runs them, and reports every runner's status before returning a failing exit code for any failed runner.

#### Scenario: One local runner fails
- **WHEN** the aggregate model regression command encounters a runner with non-zero exit status
- **THEN** the command reports the failed runner path and exits non-zero

#### Scenario: All local runners pass
- **WHEN** every discovered local runner exits zero
- **THEN** the command reports the runner count and exits zero

### Requirement: Deep validation lane
FlowGuard CI SHALL keep fast push validation separate from deep manual or scheduled validation that can run full unit tests and aggregate model regressions without slowing ordinary pushes.

#### Scenario: Push validation
- **WHEN** a commit is pushed to `main`
- **THEN** the fast validation lane runs install, project audit, OpenSpec strict validation, self-maintenance model checks, and focused tests

#### Scenario: Manual deep validation
- **WHEN** a maintainer runs the workflow manually with deep validation enabled
- **THEN** the deep lane runs full unit tests and aggregate model regressions

### Requirement: Model Shard Progress Events
Long model-regression execution SHALL emit bounded progress events containing run id, tier, shard, active model, completed/total counts, elapsed time, last terminal, and artifact location. Progress events MUST NOT be treated as completion evidence.

#### Scenario: Background full run is active
- **WHEN** the full tier continues beyond the progress interval
- **THEN** the orchestrator emits progress with completed/total counts while final status remains running

### Requirement: Per Runner And Parent Time Bounds
Each model runner SHALL have a timeout and each shard/full parent SHALL have a declared overall bound or explicit monitor policy. Timeout, cancellation, and interruption MUST create terminal child records and a non-pass parent disposition.

#### Scenario: Parent is cancelled
- **WHEN** the operator cancels an active full regression
- **THEN** active children are terminated safely, completed receipts remain preserved, and the parent reports cancelled rather than pass

### Requirement: Terminal Receipt Completeness
A long validation run SHALL emit a final receipt only after every selected child is terminal. The receipt SHALL list passed, failed, timed-out, cancelled, skipped, and not-run children, plus claim boundary and minimum rerun scope.

#### Scenario: Child process disappears without result
- **WHEN** a selected child exits or is lost without a valid terminal artifact
- **THEN** the parent records an internal/unknown child failure and cannot emit a complete passing receipt

### Requirement: Interrupted Owner Evidence Is Not Reusable
Timeout, cancellation, or interruption SHALL leave the owner receipt non-pass
and non-reusable until the complete descendant process tree is confirmed
terminated. A retry SHALL retain the original episode as failed evidence and
use one new immutable execution identity.

#### Scenario: Launcher times out with live descendants
- **WHEN** the launcher stops but a descendant process remains
- **THEN** cleanup status is unconfirmed, no receipt is reusable, and no new owner producer starts

### Requirement: Progress And Receipt Outputs Do Not Refresh Source
FlowGuard SHALL treat progress events, logs, reports, receipts, parent manifests,
and authority pointer writes as evidence outputs unless an owner explicitly declares
them as functional inputs. Their creation or mtime change MUST NOT stale source
evidence.

#### Scenario: CURRENT pointer is updated after composition
- **WHEN** an authority or evidence CURRENT pointer is written without changing consumed content
- **THEN** source-bound child receipts remain current and only pointer consumers require parity review
