## ADDED Requirements

### Requirement: TestMesh owns required contract-exhaustion child evidence
FlowGuard TestMesh MUST be able to treat canonical contract-exhaustion case ids
as required child-suite or leaf-cell evidence targets.

#### Scenario: Child suite owns generated case
- **WHEN** a parent validation claim depends on a generated contract-exhaustion
  case routed through TestMesh
- **THEN** a registered child suite or script owns the case id with current
  passing evidence

#### Scenario: Progress-only case evidence is insufficient
- **WHEN** a child suite reports only background progress for a required
  contract-exhaustion case
- **THEN** TestMesh does not count the case as completed evidence
