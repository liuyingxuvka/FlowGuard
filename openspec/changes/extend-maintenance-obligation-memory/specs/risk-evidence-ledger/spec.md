## ADDED Requirements

### Requirement: Risk ledger consumes relevant open maintenance obligations
Risk Evidence Ledger SHALL consider relevant unresolved maintenance obligations
before granting broad done, release, publish, archive, production, or full
confidence claims.

#### Scenario: Relevant open obligation blocks or scopes full confidence
- **WHEN** a risk ledger row or plan references an unresolved open obligation
  for the same risk, model, code contract, proof evidence, public entrypoint, or
  route boundary
- **THEN** `review_risk_evidence_ledger(...)` MUST block or scope full
  confidence according to the ledger scoped-confidence policy
- **AND** the finding MUST identify the open obligation

#### Scenario: Irrelevant obligation does not affect row
- **WHEN** an open obligation is anchored to a different model, code contract,
  public entrypoint, or out-of-scope artifact
- **THEN** the ledger MUST NOT use that obligation to block the unrelated risk
  row

#### Scenario: Resolved obligation needs current proof
- **WHEN** a ledger row relies on a resolved obligation
- **THEN** the resolved obligation MUST have current owner-route evidence or an
  explicit scoped disposition
- **AND** stale, missing, declaration-only, or progress-only resolution evidence
  MUST NOT support full confidence

