## ADDED Requirements

### Requirement: DevelopmentProcessFlow tracks bug repair freshness
DevelopmentProcessFlow SHALL treat bug repair changes to model-miss
classification, model obligations, owner code contracts, observed-regression
tests, same-class tests, compatibility classifications, legacy path
dispositions, and risk-ledger rows as freshness-sensitive artifacts.

#### Scenario: Later repair edit stales earlier evidence
- **WHEN** a bug repair changes the model, code contract, test evidence,
  compatibility disposition, or legacy path disposition after validation
- **THEN** DevelopmentProcessFlow marks the affected alignment, closure, and
  risk evidence stale until the owning route reruns or refreshes evidence

#### Scenario: Final claim consumes current repair evidence
- **WHEN** a final done, release, archive, publish, or broad confidence claim
  closes a bug repair
- **THEN** DevelopmentProcessFlow requires current evidence ids from Model-Miss
  Review, Model-Test Alignment, TestMesh/ModelMesh when relevant, legacy-path
  disposition when relevant, and Risk Evidence Ledger / Closure Contract
