## ADDED Requirements

### Requirement: Development process consumes primary path authority evidence
DevelopmentProcessFlow SHALL include primary-path authority as a
freshness-sensitive validation gate for staged implementation, install sync,
and final done/release claims when path-sensitive behavior is in scope.

#### Scenario: Changed fallback surface stales evidence
- **WHEN** a changed artifact adds, removes, or modifies a path, alias,
  wrapper, helper route, compatibility facade, old field, fallback candidate,
  recovery path, or migration path
- **THEN** DevelopmentProcessFlow SHALL treat prior primary-path authority,
  runtime path, coverage, TestMesh, and RiskLedger evidence as stale

#### Scenario: Final claim lacks authority evidence
- **WHEN** a final claim depends on path-sensitive behavior and has no current
  primary-path authority evidence consumed by RiskEvidenceLedger
- **THEN** DevelopmentProcessFlow SHALL report the final claim as unsupported
