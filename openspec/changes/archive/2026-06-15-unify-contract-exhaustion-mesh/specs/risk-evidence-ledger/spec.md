## ADDED Requirements

### Requirement: Risk rows consume contract-exhaustion evidence
FlowGuard RiskEvidenceLedger MUST be able to require current
ContractExhaustionMesh reports and case evidence before granting full risk
confidence for same-class or finite-boundary claims.

#### Scenario: Blocked exhaustion blocks full risk confidence
- **WHEN** a risk row depends on contract-exhaustion coverage and the report is
  blocked by missing oracles or model gaps
- **THEN** the risk row cannot report full confidence

#### Scenario: Current report supports scoped risk row
- **WHEN** all required cases for the claim have current evidence and no
  blocking findings
- **THEN** the risk row can consume the report as part of its final decision
