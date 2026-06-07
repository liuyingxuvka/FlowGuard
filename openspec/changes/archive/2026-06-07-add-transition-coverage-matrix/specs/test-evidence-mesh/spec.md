## ADDED Requirements

### Requirement: TestMesh consumes transition coverage leaf-cell requirements
TestMesh SHALL accept required leaf-cell ids derived from transition coverage matrices and require child evidence for each required transition cell.

#### Scenario: Child suite owns transition cell
- **WHEN** a TestMesh child suite is marked as leaf matrix-cell evidence and owns a transition coverage cell id
- **THEN** current passing child evidence can satisfy the parent required cell id

#### Scenario: Missing transition cell evidence blocks parent confidence
- **WHEN** a required transition coverage cell has no current passing child owner
- **THEN** TestMesh SHALL block parent confidence with a missing leaf-cell evidence finding

### Requirement: TestMesh does not decide transition semantics
TestMesh SHALL track evidence hierarchy for transition coverage cells but SHALL NOT replace Model-Test Alignment for semantic obligation coverage.

#### Scenario: Parent mesh is green but semantic claim remains scoped
- **WHEN** TestMesh child evidence is current for required cell ids
- **THEN** the mesh can support evidence freshness
- **AND** Model-Test Alignment remains responsible for whether those cells cover the declared model obligations
