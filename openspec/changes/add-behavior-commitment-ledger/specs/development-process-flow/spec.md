## ADDED Requirements

### Requirement: Broad process claims require current ledger coverage
FlowGuard SHALL require DevelopmentProcessFlow to consume Behavior Commitment
Ledger coverage before done, release, publish, archive, production, or
full-confidence claims that cover non-trivial behavior.

#### Scenario: Ledger evidence is current
- **WHEN** a staged-work report has a current behavior ledger review with no blocking findings
- **THEN** DevelopmentProcessFlow MAY treat behavior commitment coverage as satisfied for that boundary

#### Scenario: Ledger evidence is missing
- **WHEN** a broad process claim has no current behavior ledger review
- **THEN** DevelopmentProcessFlow SHALL report a freshness-sensitive validation gap

### Requirement: Behavior process work selects a ledger change mode
FlowGuard SHALL require non-trivial behavior/API/CLI/skill/template/process
work to select a behavior-ledger change mode before implementation or broad
claims.

#### Scenario: Behavior change routes to ledger mode
- **WHEN** staged work affects external behavior or its source surfaces
- **THEN** DevelopmentProcessFlow SHALL preserve the selected mode among bootstrap, add, change, remove/replace, coverage-gap backfill, or model-miss check
- **AND** stale source surfaces SHALL invalidate broad behavior claims until ledger coverage is refreshed

### Requirement: Path-sensitive process claims consume PPA through the ledger
FlowGuard SHALL require path-sensitive behavior commitments to pass PPA before
DevelopmentProcessFlow claims broad completion.

#### Scenario: PPA blocks a ledger commitment
- **WHEN** a ledger report lists a PPA-blocked commitment
- **THEN** DevelopmentProcessFlow SHALL block done, release, publish, archive, production, and full-confidence claims for the affected boundary
