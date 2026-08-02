## ADDED Requirements

### Requirement: RiskLedger owns final broad confidence
RiskLedger SHALL be the sole owner that combines verified maturation, residual risks, required evidence, and authorized scope into a final `full`, `scoped`, or `blocked` confidence decision.

#### Scenario: Maturation closes with an unresolved bounded risk
- **WHEN** the exact maturation receipt is current but a risk required for a broad claim remains unresolved
- **THEN** RiskLedger withholds full confidence and records the bounded or blocked scope
