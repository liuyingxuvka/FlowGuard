## ADDED Requirements

### Requirement: Risk ledger consumes topology hazard review evidence

FlowGuard SHALL allow each final-risk row to require a current model-topology
hazard review before broad done, release, publish, archive, or full-confidence
claims.

#### Scenario: Required topology hazard review is missing

- **GIVEN** a `RiskEvidenceRow` marks topology hazard review as required
- **WHEN** no topology hazard review id is present
- **THEN** `review_risk_evidence_ledger(...)` MUST block the broad risk claim
- **AND** it MUST report `missing_topology_hazard_review`.

#### Scenario: Blocked or scoped topology hazard evidence remains visible

- **GIVEN** a required topology hazard review id is present
- **WHEN** the review is stale, blocked, or scoped
- **THEN** the risk ledger MUST report the corresponding topology hazard
  finding
- **AND** full confidence MUST be blocked or downgraded according to ledger
  scoped-confidence policy.
