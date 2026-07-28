## ADDED Requirements

### Requirement: Canonical Validation Result Model
Every productized validation command SHALL construct one canonical result containing status, scope/tier, counts, evidence, failures, blockers, skipped checks with reasons, residual risk, claim boundary, progress summary, and artifact references. Human and JSON output MUST project the same result semantics.

#### Scenario: JSON output is requested
- **WHEN** a validation command runs with `--json`
- **THEN** it emits encoding-stable machine-readable output with no localized-only field names or human preamble

### Requirement: Concise Default And Full Trace Access
Default human output SHALL present the final status, counts, first actionable failures, blockers, and artifact locations without printing complete traces. `--full` or referenced artifacts SHALL preserve complete trace access without changing the status decision.

#### Scenario: Self-review produces large traces
- **WHEN** the full trace exceeds the concise-output threshold
- **THEN** default output summarizes it and provides the full artifact path or explicit `--full` route

### Requirement: Composable Exit And Status Semantics
Exit codes and status values SHALL distinguish pass, fail, blocked, invalid input, timeout/cancelled, and internal error. Partial/scoped/pass-with-gaps results MUST NOT return the same broad-success semantics used by full pass.

#### Scenario: Required check is not run
- **WHEN** a full validation command has a required `not_run` check
- **THEN** it returns non-success full status and a nonzero closure exit code

### Requirement: Unified Suite Validation Entrypoint
The repository SHALL expose a documented command that composes project audit, suite inventory, seventeen SkillGuard checks, evidence-bound self-governance, model regression, tests, OpenSpec verification, and distribution parity while preserving each child result and receipt.

#### Scenario: One child validation fails
- **WHEN** distribution parity fails but all other children pass
- **THEN** the unified result reports the parity child failure and blocks full/release closure

### Requirement: Frozen Owner Execution Plan
The unified full validator SHALL materialize one canonical
`ValidationInputManifest` before starting any producer. For every owner, the
manifest SHALL bind exact functional source/content identities, current
model-authority head and selected revision closure, request/purpose, toolchain,
environment policy and observed environment, check inventory, obligation
inventory, dependencies, installed consumer projection, and exactly one
execution owner. Evidence outputs SHALL be excluded unless their content is an
explicit functional input. Each owner SHALL have exactly one disposition:
`execute`, `reuse_current`, or `blocked`.

#### Scenario: Plan-only requested
- **WHEN** the caller requests plan-only mode
- **THEN** the complete owner plan and reasons are emitted and zero validation producers execute

#### Scenario: Input mapping is unknown
- **WHEN** a governed functional input cannot be mapped to exactly one owner or declared shared dependency closure
- **THEN** the plan is blocked and the validator does not fall back to run-all

#### Scenario: Only an excluded evidence output changes
- **WHEN** a log, report, progress event, receipt, or pointer output changes and no owner declares its content as a functional input
- **THEN** the `ValidationInputManifest` and reusable child identities remain unchanged

### Requirement: Cross-Run Parent Receipt Composition
The full parent SHALL accept a complete mixture of current-run and prior-run
terminal-success child receipts only after independently verifying each receipt
against the same frozen current context. Broad pass SHALL require complete
owner and obligation coverage, not execution of every child in the current run.

#### Scenario: All children are current
- **WHEN** every required child has an independently verified receipt for the frozen context
- **THEN** full validation passes by composition with zero heavy child executions

#### Scenario: Parent previously failed
- **WHEN** a parent failed because one child failed but other child receipts remain exact-current
- **THEN** the next parent may reuse the successful receipts and execute only the stale or missing child

### Requirement: Exact Single-Flight Execution Ownership
Concurrent requests for the same frozen owner identity SHALL start at most one
producer. Other callers MAY wait for its terminal receipt, but MUST independently
verify the receipt before composition.

#### Scenario: Two identical full requests overlap
- **WHEN** both requests resolve the same missing owner identity
- **THEN** one producer executes and the other request consumes the verified terminal receipt

### Requirement: Validation Reuse Telemetry
The canonical result SHALL report executed, reused, and blocked owner/model
counts, actual producer invocation counts, elapsed time, and receipt ids. These
measurements SHALL NOT alter freshness.

#### Scenario: Repeated full validation is fully reusable
- **WHEN** no functional identity changed
- **THEN** output reports zero heavy producer invocations and nonzero reused owners

### Requirement: Unique Final Full Release Gate
Release validation SHALL freeze `ValidationInputManifest`,
`ReleaseTreeManifest`, and the exact owner plan only after version `0.64.0`,
documentation, OpenSpec state, current model authority, and consumer
installation/parity are final. Exactly one final full parent gate SHALL consume
that frozen identity pair; it MAY execute stale or missing owners and reuse
independently verified exact-current receipts. Commit, tag, push, and
publication SHALL occur only after that parent passes.

#### Scenario: Version or documentation changes after the gate
- **WHEN** any post-freeze change alters either manifest before commit or tag
- **THEN** the prior final parent is invalid, publication is blocked, and a new manifest pair and affected owner plan are required

#### Scenario: Published verification starts
- **WHEN** the release commit and immutable tag already match the receipt-bound `ReleaseTreeManifest`
- **THEN** published verification performs read-only identity comparison and starts zero heavy validation producers
