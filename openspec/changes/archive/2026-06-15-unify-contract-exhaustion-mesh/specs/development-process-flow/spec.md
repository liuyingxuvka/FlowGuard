## ADDED Requirements

### Requirement: Contract-exhaustion evidence is freshness-sensitive
FlowGuard DevelopmentProcessFlow MUST treat ContractExhaustionMesh reports,
case ids, oracles, verifier artifacts, and downstream evidence as
freshness-sensitive lifecycle artifacts.

#### Scenario: Model change stales generated cases
- **WHEN** a model, field lifecycle row, payload contract, transition matrix,
  or parent-child closure model changes after contract-exhaustion evidence was
  produced
- **THEN** DevelopmentProcessFlow records the old report as stale until the
  owning evidence is regenerated or scoped

#### Scenario: Final claim consumes current report
- **WHEN** a done, release, archive, or publish claim depends on finite
  same-class or boundary exhaustion
- **THEN** DevelopmentProcessFlow requires current contract-exhaustion evidence
  and downstream route evidence before broad confidence
