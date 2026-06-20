## ADDED Requirements

### Requirement: Risk ledger consumes all-model Cartesian coverage
RiskEvidenceLedger SHALL require current all-model Cartesian coverage evidence
before granting broad done, release, publish, production, archive, or full
confidence for a FlowGuard-managed model hierarchy.

#### Scenario: Missing model receipt blocks full confidence
- **WHEN** a final risk row requires all-model Cartesian coverage
- **AND** any in-scope model lacks a current coverage receipt
- **THEN** RiskEvidenceLedger reports a missing model coverage finding
- **AND** full confidence is blocked

#### Scenario: Unclosed shard blocks full confidence
- **WHEN** a final risk row depends on a coverage receipt with unfinished
  required shards
- **THEN** RiskEvidenceLedger reports unclosed Cartesian shard evidence
- **AND** full confidence is blocked or scoped according to policy

#### Scenario: Complete all-model coverage supports confidence
- **WHEN** every in-scope model receipt is current
- **AND** every required generated case has semantic and test evidence
- **AND** every child receipt is consumed by its parent
- **THEN** RiskEvidenceLedger may treat all-model Cartesian coverage as
  supporting final confidence

### Requirement: Ledger rejects child-local coverage bypass
RiskEvidenceLedger SHALL reject final confidence when a claim cites child-local
Cartesian coverage but no parent ModelMesh evidence consumed that child
coverage.

#### Scenario: Child local receipt bypasses parent mesh
- **WHEN** a risk row cites a child coverage receipt directly for a parent or
  root claim
- **AND** no current parent consumption evidence exists
- **THEN** RiskEvidenceLedger reports unconsumed child coverage
