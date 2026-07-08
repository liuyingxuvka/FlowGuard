## ADDED Requirements

### Requirement: ContractExhaustionMesh remains canonical after route cleanup
ContractExhaustionMesh SHALL remain the only canonical route for generated
finite bad-case ids after helper-control-plane consolidation.

#### Scenario: Feeder case is projected
- **WHEN** StateClosure, ScenarioMatrix, ObligationFamily, ModelMissReview,
  ArtifactPayload, TransitionCoverage, or ModelMesh closure finds a bad-case
  seed
- **THEN** the seed MUST be projected to `ContractMutationCase` before it can
  support canonical finite-boundary coverage

#### Scenario: Old helper case id is cited
- **WHEN** a claim cites only an old helper-generated case id
- **THEN** ContractExhaustionMesh MUST treat that evidence as seed evidence or
  incomplete coverage, not canonical coverage

### Requirement: Composite handoff acceptance remains separate
ContractExhaustionMesh SHALL keep composite handoff acceptance separate from
matrix readiness.

#### Scenario: Generated case crosses routes
- **WHEN** a generated case must be consumed by Model-Test Alignment, TestMesh,
  ModelMesh, RiskEvidenceLedger, or DevelopmentProcessFlow
- **THEN** the report MUST expose a composite handoff acceptance id that the
  relevant owner routes can close
