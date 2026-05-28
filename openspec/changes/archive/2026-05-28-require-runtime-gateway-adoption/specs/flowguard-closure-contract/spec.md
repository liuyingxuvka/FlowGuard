# flowguard-closure-contract Delta

## MODIFIED Requirements

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
