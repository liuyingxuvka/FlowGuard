# risk-evidence-ledger Delta

## MODIFIED Requirements

### Requirement: Risk rows can require family parity gates

Risk Evidence Ledger SHALL let a risk row require a current family parity gate before full confidence is granted.

#### Scenario: Missing family gate blocks confidence
- **WHEN** a required risk row declares that a family parity gate is required
- **AND** no family gate id is present
- **THEN** the ledger reports a missing family gate finding.

#### Scenario: Blocked family gate blocks confidence
- **WHEN** a required risk row references a family gate with blocked confidence
- **THEN** the ledger blocks full confidence for that risk.

#### Scenario: Scoped family gate remains scoped
- **WHEN** a required risk row references a family gate with scoped or partial confidence
- **THEN** the ledger reports scoped confidence
- **AND** if scoped confidence is not allowed, the ledger blocks the claim.

### Requirement: Risk rows can require analogous defect scan gates

Risk Evidence Ledger SHALL let a risk row require a current analogous defect scan before full confidence is granted after a model miss.

#### Scenario: Missing analogous scan blocks confidence
- **WHEN** a required risk row declares that an analogous defect scan is required
- **AND** no analogous scan id is present
- **THEN** the ledger reports a missing analogous scan finding.

#### Scenario: Blocked analogous scan blocks confidence
- **WHEN** a required risk row references an analogous defect scan with blocked confidence
- **THEN** the ledger blocks full confidence for that risk.

#### Scenario: Scoped analogous scan remains scoped
- **WHEN** a required risk row references an analogous defect scan with scoped or partial confidence
- **THEN** the ledger reports scoped confidence
- **AND** if scoped confidence is not allowed, the ledger blocks the claim.
