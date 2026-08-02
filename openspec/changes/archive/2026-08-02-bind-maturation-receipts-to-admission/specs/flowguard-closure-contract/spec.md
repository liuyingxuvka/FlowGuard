## ADDED Requirements

### Requirement: Closure validates identity and terminal integrity without recomputing confidence
ClosureContract SHALL verify that the TaskCoverageDemand, maturation receipt, admission result, RiskLedger decision, and required terminal evidence share exact identities and materially agree. It SHALL preserve the RiskLedger confidence decision rather than deriving another one.

#### Scenario: Closure inputs disagree on demand identity
- **WHEN** downstream artifacts refer to different coverage-demand fingerprints
- **THEN** closure fails with an identity mismatch regardless of each artifact's local status
