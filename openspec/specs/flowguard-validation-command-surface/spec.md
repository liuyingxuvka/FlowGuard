# flowguard-validation-command-surface Specification

## Purpose
Define one composable validation surface that plans exact owners, reuses current evidence, and binds a frozen release claim.
## Requirements
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
The repository SHALL expose a documented command that composes project audit,
package-authority-derived suite inventory, every target-declared native
skill-owner check, evidence-bound self-governance, model regression, tests,
OpenSpec verification, and distribution parity while preserving each child
result and receipt. A fixed historical member/check count MUST NOT define the
owner inventory.

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
`ReleaseTreeManifest`, and the exact owner plan only after the selected current
version identity, documentation, OpenSpec state, current model authority, and
consumer installation/parity are final. Exactly one final full parent gate
SHALL consume that frozen identity pair; it MAY execute stale or missing
owners and reuse independently verified exact-current receipts. Commit, tag,
push, and publication SHALL occur only after that parent passes.

#### Scenario: Version or documentation changes after the gate
- **WHEN** any post-freeze change alters either manifest before commit or tag
- **THEN** the prior final parent is invalid, publication is blocked, and a new manifest pair and affected owner plan are required

#### Scenario: Published verification starts
- **WHEN** the release commit and immutable tag already match the receipt-bound `ReleaseTreeManifest`
- **THEN** published verification performs read-only identity comparison and starts zero heavy validation producers

### Requirement: Model-understanding status command is read-only and composable
The command surface SHALL expose a model-understanding status command that consumes exact artifact references and returns structured understanding sufficiency, FlowGuard implementation admission, user choice, identity mismatches, and not-run gaps. The command SHALL NOT execute validation owners, resume a run, publish evidence, modify files, or change authority.

#### Scenario: Required artifact reference is absent
- **WHEN** the command is invoked without a required current artifact reference
- **THEN** it returns an explicit not-run or unresolved gap and performs no write

#### Scenario: Complete matching artifact set is supplied
- **WHEN** all supplied artifacts have matching current identities and terminal evidence
- **THEN** the command deterministically reports the licensed status with a successful read-only exit

### Requirement: Blueprint command surfaces use one qualification owner over the native directory
The command surface SHALL provide a read-only implementation-inventory audit and canonical target/project blueprint audits over the current native model directory. Read-only commands SHALL NOT write artifacts, publish evidence, change model authority, execute missing owners, create a copied directory, or create a bundle/materialization.

#### Scenario: Read-only project blueprint audit finds missing evidence
- **WHEN** a project blueprint audit lacks a required current binding or resource
- **THEN** it reports the exact incomplete or stale gap and performs no write or owner execution

#### Scenario: Standalone project projection is requested
- **WHEN** a caller supplies an output path for a project projection, bundle, or materialization
- **THEN** the command returns `native_directory_only`, writes nothing, and keeps
  `model_readiness_status` separate from any not-run execution evidence

#### Scenario: Standalone target projection is requested
- **WHEN** a caller invokes `target-system-blueprint-export` or supplies an output
  path for a target projection
- **THEN** the command returns `native_directory_only`, writes nothing, and
  preserves blocked or not-run evidence in the in-place audit result

### Requirement: The target blueprint audit is the single read-only status command
The command surface SHALL provide one provider-neutral target-system blueprint audit operation for an explicit target descriptor, frozen provider evidence, and current native report set. The same operation SHALL return both the canonical machine-readable qualification report and composable `0|1|2` exit semantics. It SHALL NOT have a duplicate check alias, write a projection, modify the target, install software, or execute a missing provider.

#### Scenario: A declared workflow blueprint audit is requested
- **WHEN** a caller supplies a bounded workflow target and current observation and authority provider results
- **THEN** the command returns canonical machine-readable provider, lineage, evidence, and depth findings without requiring a programming language
- **AND** the target artifacts and authority pointers remain unchanged

#### Scenario: A target boundary lacks a deep provider
- **WHEN** audit reaches a required source, workflow, trace, resource, or authority boundary for which no registered current provider supplies the required capability
- **THEN** the command returns a non-pass result naming the exact boundary and missing provider capability
- **AND** it does not fall back to FlowGuard's Python self preset or another shallow adapter

#### Scenario: FlowGuard self-blueprint and reduction are requested together
- **WHEN** the self-blueprint check receives the explicit composed architecture-reduction option
- **THEN** it builds one current self-blueprint and returns both compact bounded results from that exact bundle
- **AND** it does not rebuild the blueprint, write a cache, or modify source
### Requirement: Audit is the only DNA status action
Read-only target/project audit SHALL report the current model depth and exact gaps without writing target or projection artifacts. Former target/project export, bundle, copied-directory, and isolated-verification actions are retired and SHALL return `native_directory_only`.

#### Scenario: Audit is used during ordinary maintenance
- **WHEN** ordinary affected-only maintenance invokes a target or project blueprint audit
- **THEN** it reports the licensed current understanding and writes no projection

#### Scenario: Retired export is explicitly requested
- **WHEN** a caller explicitly requests export for strict target artifacts or a
  canonically assembled project bundle
- **THEN** the action fails with `native_directory_only`, writes no projection,
  and leaves every model gap and not-run status in the audit result

### Requirement: Candidate blueprint discovery is read-only
FlowGuard SHALL expose a composable read-only command for candidate blueprint discovery. It SHALL perform no target-source edits, export, missing-owner execution, installation, or authority activation; canonical audit owns readiness and gap reporting.

#### Scenario: Candidate command finds unresolved semantics
- **WHEN** candidate discovery cannot independently establish one or more behavior contracts
- **THEN** the command SHALL return a nonzero or explicit incomplete terminal with all unresolved ids
- **AND** it SHALL write no project artifact

### Requirement: Validation status identifies parent versus child authority
Validation status output SHALL identify whether a current pointer belongs to a child or terminal parent and SHALL reject a child result as evidence for an incomplete parent gate.

#### Scenario: Child current file is passed to parent verifier
- **WHEN** a verifier receives a current pointer whose authority kind is `child`
- **THEN** parent verification SHALL fail with a typed authority-kind mismatch

### Requirement: Native member resume is explicit execution with exact-current reuse
The native-skill validation command SHALL expose an explicit resume operation that independently verifies every candidate member receipt and reuses it only when the receipt is terminal pass, full scope, and exact-current for the declared member inputs. Every missing, stale, failed, timed-out, blocked, partial, or unverifiable member SHALL execute its one declared owner or remain visibly non-pass.

#### Scenario: Identical native member is reused
- **WHEN** a member has an independently verified terminal-pass full receipt whose command, obligations, contract, manifest, suite inventory, declared inputs, producer, toolchain, environment, proof, and result identities all match the current invocation
- **THEN** resume SHALL report that member as `reuse_current` and SHALL NOT execute its native commands again

#### Scenario: One declared input changes
- **WHEN** any declared native command input or producer source differs from the receipt-bound snapshot
- **THEN** resume SHALL execute that member's declared owner and SHALL NOT reuse the stale receipt

#### Scenario: Resume has no fallback
- **WHEN** a candidate receipt is damaged, ambiguous, non-terminal, non-pass, partial, or cannot be verified against current inputs
- **THEN** the command SHALL NOT select an older schema, alternate store, compatibility reader, alias, or inferred success

### Requirement: Native receipts bind the complete declared input set
Each native member receipt SHALL bind every declared native command and exact path selector, the receipt producer sources, the compiled contract, check manifest, suite inventory, covered obligations, toolchain, environment, proof artifact, and result identity used by that member.

#### Scenario: Later declared command is part of currentness
- **WHEN** a member declares more than one native command
- **THEN** files selected by every command SHALL participate in the receipt's exact-current verification rather than only files selected by the first command

#### Scenario: Declared input set changes
- **WHEN** the recomputed current input artifact set is not exactly the receipt-bound artifact set
- **THEN** the receipt SHALL be ineligible for reuse even if all common files retain matching hashes

### Requirement: Native execution accounting remains visible
The native command's terminal report SHALL separately expose requested, passed, executed, and reused member counts and SHALL preserve the disposition and receipt identity for every selected member.

#### Scenario: Mixed execute and reuse
- **WHEN** some selected members have exact-current receipts and others are missing or stale
- **THEN** the terminal report SHALL distinguish the reused members from the executed members and SHALL retain every non-pass member result
