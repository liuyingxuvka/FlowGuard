## ADDED Requirements

### Requirement: TestMesh rejects invalid reused child suite evidence
TestMesh SHALL reject reused child-suite evidence before that suite supports a
parent test gate unless the suite has a current test-result reuse ticket and a
current proof artifact.

#### Scenario: Reused child suite supports parent
- **WHEN** a child suite is marked as reused
- **AND** its reuse ticket and proof artifact are current
- **AND** the suite otherwise has current passing evidence
- **THEN** TestMesh MAY count that child suite toward parent confidence

#### Scenario: Reused child suite lacks proof
- **WHEN** a child suite is marked as reused but has no reuse ticket or no
  proof artifact
- **THEN** TestMesh SHALL report a reuse-proof finding
- **AND** the child suite SHALL NOT support parent green confidence

#### Scenario: Background progress is not reusable completion
- **WHEN** a reused child suite only has progress output or lacks final
  background exit/result artifacts
- **THEN** TestMesh SHALL report incomplete background evidence rather than
  accepting the old result
