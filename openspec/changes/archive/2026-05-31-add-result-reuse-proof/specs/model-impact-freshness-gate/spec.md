## ADDED Requirements

### Requirement: Model and test reuse follow the same current-evidence principle
FlowGuard SHALL document model-result reuse and test-result reuse as separate
ticket types governed by the same principle: unchanged evidence may be reused
only when the owning ticket and concrete result artifact are current.

#### Scenario: Model result reuse remains model-owned
- **WHEN** model output is not impacted by a framework or artifact change
- **THEN** model reuse SHALL continue to use `ModelReuseTicket`

#### Scenario: Test result reuse is test-owned
- **WHEN** a previous test result is reused for current model/test alignment or
  TestMesh confidence
- **THEN** test reuse SHALL use a test-result reuse ticket plus proof artifact
  rather than a model reuse ticket
