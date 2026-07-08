## ADDED Requirements

### Requirement: Risk ledger gates behavior commitment coverage
FlowGuard SHALL expose a behavior-commitment coverage risk gate and SHALL
block broad confidence when required ledger coverage is missing or blocked.

#### Scenario: Ledger gate passes
- **WHEN** a RiskEvidenceLedger row references a current passing behavior ledger report
- **THEN** the risk gate SHALL be eligible to support broad confidence

#### Scenario: Ledger gate blocks
- **WHEN** a RiskEvidenceLedger row references missing, stale, or blocked behavior ledger coverage
- **THEN** the risk gate SHALL block release, publish, archive, production, and full-confidence claims
