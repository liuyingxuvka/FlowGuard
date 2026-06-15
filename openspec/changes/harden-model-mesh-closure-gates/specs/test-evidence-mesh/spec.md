## ADDED Requirements

### Requirement: TestMesh owns ModelMesh-derived leaf-cell evidence
TestMesh SHALL require current child-suite evidence for every required
ModelMesh-derived transition leaf-cell id before a parent validation gate can
support parent confidence.

#### Scenario: ModelMesh-derived cell has no child owner
- **WHEN** a TestMesh parent gate declares required leaf-cell ids generated from
  ModelMesh closure transitions
- **AND** no registered child suite owns one of those ids
- **THEN** TestMesh SHALL report missing leaf-cell evidence
- **AND** parent validation confidence SHALL be blocked

#### Scenario: Child suite owns retry/rejection cell
- **WHEN** a child suite owns a ModelMesh-derived retry/rejection leaf-cell id
- **AND** the suite has current passing evidence and final background artifacts
- **THEN** TestMesh MAY count that child evidence for parent evidence freshness
- **AND** Model-Test Alignment SHALL still own semantic model/code/test binding
