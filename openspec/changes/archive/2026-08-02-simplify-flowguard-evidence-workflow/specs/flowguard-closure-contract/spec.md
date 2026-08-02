## ADDED Requirements

### Requirement: Closure is a thin terminal integrity boundary
ClosureContract SHALL validate final identity continuity, required material presence, terminal evidence integrity, and agreement with the RiskLedger decision. It SHALL NOT repeat route-specific maturation, installation, test, or risk-scoring logic.

#### Scenario: All upstream decisions agree
- **WHEN** exact identities match, required materials are present, terminal evidence verifies, and RiskLedger is terminal
- **THEN** closure preserves the RiskLedger confidence and reports integrity success without recomputation
