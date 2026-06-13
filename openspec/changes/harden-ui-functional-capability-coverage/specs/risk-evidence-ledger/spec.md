## ADDED Requirements

### Requirement: Risk ledger consumes UI functional capability coverage
RiskEvidenceLedger SHALL provide a UI functional capability coverage gate for final UI done, release, or runnable-confidence claims.

#### Scenario: Capability gate supports confidence
- **WHEN** every in-scope required UI capability has current coverage, output contract evidence, implementation binding evidence, and accepted scope boundaries
- **THEN** the risk ledger may treat UI capability coverage as supporting evidence for the declared UI claim

#### Scenario: Capability gate is missing or scoped
- **WHEN** the UI capability coverage gate is missing, stale, failed, planned-only, or scoped below the final claim
- **THEN** the risk ledger blocks or scopes final UI confidence instead of accepting visible-control or screenshot evidence alone
