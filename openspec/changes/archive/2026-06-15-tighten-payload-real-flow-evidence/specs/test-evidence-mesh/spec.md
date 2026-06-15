## ADDED Requirements

### Requirement: TestMesh preserves payload execution proof
TestMesh SHALL preserve payload contract ids, case ids, result artifact paths,
and execution proof references when it owns large payload validation matrices.

#### Scenario: Payload child suite feeds alignment
- **WHEN** a child suite owns a payload case for a file/work-package surface
- **THEN** the child suite evidence MUST identify the real surface execution
  proof that Model-Test Alignment can consume
- **AND** TestMesh MUST NOT treat case ownership alone as semantic payload
  proof
