## ADDED Requirements

### Requirement: Bug repair fixes primary path instead of adding fallback
Post-runtime Model Miss Review SHALL require bug repairs to backpropagate the
observed miss to the primary path and reject alternate success paths as closure
evidence.

#### Scenario: Fallback fix is rejected
- **WHEN** a bug repair makes the failing scenario pass by invoking an
  alternate path after primary failure
- **THEN** Model Miss Review SHALL report that primary path repair evidence is
  missing

#### Scenario: Primary path repair closes miss
- **WHEN** the root-cause model, owner code contract, replay evidence,
  same-class generated cases, and legacy/fallback disposition all point to the
  repaired primary path
- **THEN** Model Miss Review MAY treat the repair as eligible for downstream
  ledger closure
