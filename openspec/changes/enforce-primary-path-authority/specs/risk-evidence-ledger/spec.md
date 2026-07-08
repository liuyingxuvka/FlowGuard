## ADDED Requirements

### Requirement: Risk ledger consumes primary path authority
RiskEvidenceLedger SHALL support a primary-path authority gate for final risk
rows that depend on path-sensitive behavior.

#### Scenario: Missing authority gate blocks broad confidence
- **WHEN** a final risk row requires primary-path authority
- **AND** no current primary-path authority evidence id is attached
- **THEN** the ledger SHALL report a missing primary-path authority gate

#### Scenario: Blocked authority evidence blocks confidence
- **WHEN** a final risk row references primary-path authority evidence with
  blocked findings
- **THEN** the ledger SHALL block or scope confidence according to ledger
  policy

### Requirement: Risk ledger consumes primary-path Cartesian coverage
RiskEvidenceLedger SHALL require current primary-path Cartesian coverage
receipts before granting broad confidence for no-fallback claims.

#### Scenario: Missing primary-path coverage receipt blocks
- **WHEN** a risk row requires primary-path Cartesian coverage
- **AND** a required coverage receipt or shard id is missing, stale, skipped,
  progress-only, or unconsumed
- **THEN** the ledger SHALL report a primary-path Cartesian coverage gap

#### Scenario: Current authority and coverage support closure
- **WHEN** primary-path authority evidence is current and all required coverage
  receipts, shards, and composite handoff ids are consumed
- **THEN** the ledger MAY use those evidence rows to support the declared
  path-sensitive confidence boundary
