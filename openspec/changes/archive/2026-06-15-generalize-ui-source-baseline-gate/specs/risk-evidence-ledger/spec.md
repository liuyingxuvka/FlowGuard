## ADDED Requirements

### Requirement: Risk ledger consumes UI source-baseline evidence
RiskEvidenceLedger SHALL support a generic UI source-baseline interaction gate for source-based UI risks where missing source inventory, unapproved target drift, missing interaction branches, no-handler controls, or observed-source mismatch can invalidate a broad UI claim.

#### Scenario: Source-based UI risk lacks baseline proof
- **WHEN** a required UI risk depends on source-based parity or approved source differences
- **AND** no current source-baseline, target mapping, or observed-source alignment evidence is linked
- **THEN** the risk ledger blocks broad UI done/release confidence

#### Scenario: Source-baseline gate is blocked
- **WHEN** a required UI risk references a blocked or stale source-baseline interaction gate
- **THEN** the risk ledger blocks or scopes the risk according to the ledger confidence policy

### Requirement: Risk ledger uses generic source-baseline gate names
RiskEvidenceLedger SHALL use generic source-baseline gate constants and findings in public APIs, docs, and templates.

#### Scenario: Risk gate names one source technology
- **WHEN** a current risk gate constant, finding code, docs row, or template names one source technology as the generic UI source evidence gate
- **THEN** the risk ledger surface is incomplete until the name is generalized
