# flowguard-closure-contract Specification

## Purpose
Define the final evidence boundary for complete FlowGuard use. The closure
contract keeps broad done, release, publish, and production-confidence claims
from being promoted from model-only, test-only, stale, scoped, or unconsumed
route evidence.
## Requirements
### Requirement: Complete FlowGuard Use Requires Closure Contract

FlowGuard SHALL define complete use as a mandatory closure contract rather than
an optional mode. Complete FlowGuard use SHALL distinguish design-only,
test-aligned, and runtime-gateway claims. When the user-facing claim says
production state mutation is protected by FlowGuard, the closure contract SHALL
require current Runtime Gateway Adoption evidence.

#### Scenario: Full-confidence claim has closure evidence

- **GIVEN** a task claims done, release, publish, or production confidence after
  FlowGuard use
- **AND** the claim crosses model, code, test, process, UI, mesh, adapter, or
  evidence boundaries
- **WHEN** FlowGuard guidance reviews the claim
- **THEN** the claim requires current closure evidence for plan/risk intake,
  model ownership or model creation, model-test/code alignment when code or
  tests are in scope, same-class model-miss evidence when a miss was repaired,
  runtime gateway adoption when production state mutation is claimed, mesh or
  boundary proof when parent/child evidence is in scope, evidence freshness,
  Risk Evidence Ledger, and typed claim-chain review

#### Scenario: Partial evidence cannot be called complete FlowGuard use

- **GIVEN** a model or test run passed
- **AND** a required closure gate is missing, stale, skipped, progress-only, or
  explicitly scoped out
- **WHEN** the result is reported
- **THEN** the report marks the work as partial/scoped FlowGuard evidence
  instead of saying FlowGuard completion or full confidence

#### Scenario: Runtime protection claim needs gateway adoption
- **WHEN** a project claims FlowGuard protects critical runtime state writes
- **THEN** the closure contract SHALL require a current runtime-gateway
  adoption report
- **AND** a design model, model-test alignment report, or code-boundary report
  alone SHALL NOT satisfy that claim

#### Scenario: Scoped claim can stay below runtime-gateway level
- **WHEN** a project only claims design guidance or test alignment
- **THEN** FlowGuard SHALL allow the claim to remain scoped to that lower level
- **AND** it SHALL NOT describe the runtime as protected by FlowGuard

### Requirement: Thin Entry Path Does Not Replace Closure

The lightweight model-first path SHALL remain an entry path and SHALL NOT be
described as sufficient for broad completion claims by itself.

#### Scenario: Small local risk stays small

- **GIVEN** a small task only claims a bounded model-level decision
- **WHEN** the thin path runs one fit-for-risk model and evidence remains
  inside that local claim
- **THEN** the report may stay bounded without invoking unrelated framework
  suites

#### Scenario: Broad claim escalates

- **GIVEN** a task starts with the thin path
- **AND** the final statement would claim real code, tests, release readiness,
  parent/child model confidence, or production confidence
- **WHEN** the claim is made
- **THEN** the required closure routes must be consumed before full confidence
  is allowed

### Requirement: Model Misses Upgrade The Closure Contract

FlowGuard SHALL treat every post-green bug as evidence that the previous
closure contract was too narrow until the miss is backpropagated.

#### Scenario: Bug escapes after green evidence

- **GIVEN** runtime, test, replay, log, or manual evidence fails after an
  earlier FlowGuard pass
- **WHEN** FlowGuard reviews the failure
- **THEN** Model-Miss Review records the observed failure and at least one
  same-class generalized bad case when practical, Model-Test Alignment binds
  current observed-regression and same-class test evidence, and the final Risk
  Evidence Ledger/claim-chain boundary marks prior evidence stale or
  overclaimed until the repaired obligation is current

### Requirement: Installed And Source Surfaces Stay Synchronized

FlowGuard SHALL treat public skill-guidance changes as incomplete until source,
installed, editable-install, shadow workspace, and version surfaces are
synchronized or explicitly reported as scoped.

#### Scenario: Skill contract changes

- **GIVEN** a change modifies FlowGuard skill guidance or public documentation
- **WHEN** the change is completed locally
- **THEN** source files, installed Codex skill copies, editable package import,
  shadow workspace import, and visible version metadata are checked for
  alignment before the final completion claim

### Requirement: Executable Closure Contract Review

FlowGuard SHALL provide an executable closure contract review for broad done,
release, publish, or production-confidence claims.

#### Scenario: All required closure evidence is current

- **WHEN** a closure plan has current runtime trace mapping, artifact freshness,
  model quality, same-class miss, runtime gateway, and risk ledger evidence for
  every required in-scope item
- **THEN** the review returns full confidence

#### Scenario: Required closure evidence is missing

- **WHEN** a closure plan omits a required in-scope evidence area
- **THEN** the review blocks full confidence and reports the missing area

### Requirement: Runtime Trace Model Mapping

FlowGuard SHALL require runtime traces used for production confidence to map to
declared model obligations.

#### Scenario: Runtime trace maps to model obligation

- **WHEN** a runtime trace row is current, in scope, and names a model obligation
- **THEN** the closure review accepts the trace mapping evidence

#### Scenario: Runtime trace has no model obligation

- **WHEN** an in-scope runtime trace row has no model obligation
- **THEN** the closure review reports the trace as a model-miss boundary

### Requirement: Artifact Invalidation Review

FlowGuard SHALL treat changed artifacts as invalidation evidence for dependent
model, test, gateway, code-boundary, and ledger proof.

#### Scenario: Changed artifact has revalidation evidence

- **WHEN** an artifact invalidation row names changed artifacts and has current
  revalidation evidence for the dependent proof
- **THEN** the closure review accepts the freshness evidence

#### Scenario: Changed artifact lacks revalidation evidence

- **WHEN** an artifact invalidation row marks prior proof stale or lacks current
  revalidation evidence
- **THEN** the closure review blocks full confidence

### Requirement: Model Quality Signals

FlowGuard SHALL surface model-quality gaps before broad confidence is claimed.

#### Scenario: Model quality signals are resolved

- **WHEN** hidden state, missing side-effect, owner ambiguity, helper-only proof,
  missing public boundary, and parent-child evidence signals are either absent
  or resolved
- **THEN** the closure review accepts model-quality evidence

#### Scenario: Model is too coarse

- **WHEN** a required in-scope model-quality signal remains unresolved
- **THEN** the closure review blocks full confidence or downgrades to scoped
  confidence when scoped claims are allowed

### Requirement: Same-Class Model Miss Closure

FlowGuard SHALL require in-scope runtime/model misses to include observed
failure evidence and same-class closure evidence before broad confidence is
restored.

#### Scenario: Same-class miss closure passes

- **WHEN** a model-miss closure row names the observed failure and current
  same-class proof evidence
- **THEN** the closure review accepts the miss closure

#### Scenario: Same-class proof is missing

- **WHEN** an in-scope model-miss closure row lacks same-class proof evidence
- **THEN** the closure review blocks full confidence

### Requirement: Runtime Gateway Inventory Closure

FlowGuard SHALL require runtime-gateway confidence to include writer inventory
source evidence, gateway coverage, and resolved path-owner conflicts.

#### Scenario: Runtime gateway inventory is complete

- **WHEN** a runtime gateway closure row names current inventory source evidence,
  current gateway adoption evidence, and no unresolved path-owner conflicts
- **THEN** the closure review accepts runtime gateway support

#### Scenario: Runtime gateway inventory source is missing

- **WHEN** a runtime gateway closure row lacks current inventory source evidence
- **THEN** the closure review blocks runtime-protected confidence

#### Scenario: Runtime gateway path-owner conflict remains open

- **WHEN** a runtime gateway closure row has unresolved path-owner conflicts
- **THEN** the closure review blocks full confidence

### Requirement: Risk Ledger Final Boundary

FlowGuard SHALL require Risk Evidence Ledger support before reporting full
confidence for a broad claim.

#### Scenario: Risk ledger supports full confidence

- **WHEN** a closure plan includes a current risk ledger report with full
  confidence
- **THEN** the closure review may return full confidence if all other required
  gates pass

#### Scenario: Risk ledger is scoped or missing

- **WHEN** a closure plan has no risk ledger evidence or only scoped risk ledger
  confidence
- **THEN** the closure review blocks or scopes the final claim according to the
  plan's scoped-claim policy

### Requirement: Closure contract consumes runtime path alignment
FlowGuard Closure Contract SHALL consume runtime path alignment reports when a
broad done, release, publish, parent/child, or production-confidence claim
depends on real code following a modeled workflow path.

#### Scenario: Runtime path alignment supports full confidence
- **WHEN** a closure plan requires runtime path evidence
- **AND** the closure evidence includes a current full-confidence runtime path
  alignment report
- **THEN** runtime path alignment SHALL NOT block full closure confidence

#### Scenario: Runtime path alignment is missing
- **WHEN** a closure plan requires runtime path evidence
- **AND** no current runtime path alignment report is supplied
- **THEN** closure review SHALL block or scope the final confidence claim

#### Scenario: Runtime path alignment is scoped
- **WHEN** runtime path alignment is current but only scoped
- **THEN** closure review SHALL NOT promote that evidence to full production or
  parent confidence
